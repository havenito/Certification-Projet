from flask import Blueprint, request, jsonify, current_app
import stripe
import os
from models import db
from models.subscription import Subscription
from models.user import User
from datetime import datetime

subscriptions_bp = Blueprint('subscriptions', __name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Mapping obligatoire entre nos clés de plans et les vrais Price ID générés sur le dashboard Stripe
PRICE_MAP = {
    "plus": "price_1ROyhCQ4HFaTDsy2ltML3IKu",
    "premium": "price_1ROyhzQ4HFaTDsy2roH3gom5"
}

SUBSCRIPTION_TYPES = ['free', 'plus', 'premium']
SUBSCRIPTION_STATUS_TYPES = ['active', 'canceled']


def validate_subscription_type(subscription_type):
    """ Sécurité pour vérifier que le plan demandé correspond bien aux types autorisés par notre ENUM """
    if subscription_type not in SUBSCRIPTION_TYPES:
        raise ValueError(f"Type d'abonnement invalide: {subscription_type}. Valeurs autorisées: {SUBSCRIPTION_TYPES}")
    return subscription_type


def validate_subscription_status(status):
    """ Même chose pour les statuts, on bloque si Stripe renvoie un truc qui n'est pas géré """
    if status not in SUBSCRIPTION_STATUS_TYPES:
        raise ValueError(f"Statut d'abonnement invalide: {status}. Valeurs autorisées: {SUBSCRIPTION_STATUS_TYPES}")
    return status


# ============================================================
# Route : créer une session de paiement Stripe Checkout
# Redirige l'utilisateur vers la page de paiement hébergée par Stripe
# ============================================================
@subscriptions_bp.route('/api/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """ Point d'entrée pour envoyer l'utilisateur sur la page de paiement sécurisée de Stripe """
    try:
        data = request.get_json()
        plan_id = data.get("planId")
        user_id = data.get("userId")
        # Origin utilisé pour construire les URLs de retour (succès/annulation),
        # avec un fallback sur localhost en cas d'absence d'en-tête (dev local)
        origin = request.headers.get("Origin", "http://localhost:3000")

        if plan_id not in PRICE_MAP:
            return jsonify({'error': f'Plan inconnu: {plan_id}. Plans disponibles: {list(PRICE_MAP.keys())}'}), 400

        try:
            validate_subscription_type(plan_id)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        # Sécurité pour éviter les doubles abonnements payants simultanés
        existing_subscription = Subscription.query.filter_by(
            user_id=user_id,
            status='active'
        ).first()

        if existing_subscription:
            return jsonify({'error': 'Vous avez déjà un abonnement actif. Veuillez d\'abord le résilier avant de souscrire à un nouveau plan.'}), 400

        # On génère la session Stripe avec les métadonnées pour savoir qui paye quoi lors du retour webhook
        # (le webhook checkout.session.completed relira ces metadata pour créer l'abonnement en base)
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{
                "price": PRICE_MAP[plan_id],
                "quantity": 1
            }],
            metadata={
                "user_id": str(user_id),
                "plan": plan_id
            },
            customer_email=user.email,
            success_url=f"{origin}/premium?success=1&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/premium?canceled=1"
        )

        return jsonify({"url": session.url})

    except Exception as e:
        current_app.logger.error(f"Erreur création session Stripe: {e}")
        return jsonify({'error': 'Erreur lors de la création de la session'}), 500


# ============================================================
# Route : webhook Stripe — point d'entrée pour tous les événements asynchrones
# envoyés par Stripe (paiement réussi, abonnement mis à jour/supprimé, etc.)
#
# C'est Stripe qui appelle cette route directement (pas le frontend), donc la
# vérification de signature (stripe.Webhook.construct_event) est essentielle :
# elle garantit que la requête vient bien de Stripe et n'a pas été falsifiée
# par un tiers qui aurait deviné l'URL de ce webhook.
# ============================================================
@subscriptions_bp.route('/api/webhook', methods=['POST'])
def stripe_webhook():
    """ Réception des événements asynchrones envoyés par Stripe (paiements, annulations, etc.) """
    payload = request.data
    sig_header = request.headers.get("stripe-signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    # On valide que la requête vient bien de Stripe et que le contenu n'a pas été altéré
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        # Payload illisible / mal formé
        current_app.logger.error("Payload invalide reçu du webhook Stripe")
        return "Invalid payload", 400
    except stripe.error.SignatureVerificationError:
        # La signature ne correspond pas : la requête ne vient probablement pas de Stripe
        current_app.logger.error("Signature invalide du webhook Stripe")
        return "Invalid signature", 400

    # Dispatch de l'événement vers la bonne fonction interne selon le type notifié par Stripe
    try:
        if event["type"] == "checkout.session.completed":
            # Premier paiement réussi -> création de l'abonnement en base
            handle_checkout_completed(event["data"]["object"])

        elif event["type"] == "invoice.payment_succeeded":
            # Renouvellement mensuel réussi -> on s'assure que le statut reste 'active'
            handle_payment_succeeded(event["data"]["object"])

        elif event["type"] == "customer.subscription.updated":
            # Changement de statut/dates côté Stripe (ex: passage en impayé)
            handle_subscription_updated(event["data"]["object"])

        elif event["type"] == "customer.subscription.deleted":
            # Abonnement définitivement supprimé côté Stripe -> retour au plan gratuit
            handle_subscription_deleted(event["data"]["object"])

        # Note : tous les autres types d'événements Stripe non listés ici sont silencieusement
        # ignorés (la fonction retourne quand même 200 "Success" pour éviter que Stripe ne les
        # renvoie en boucle), ce qui est le comportement attendu pour un webhook qui ne traite
        # qu'un sous-ensemble d'événements

        return "Success", 200

    except Exception as e:
        current_app.logger.error(f"Erreur webhook Stripe: {e}")
        return "Error", 500


def handle_checkout_completed(session):
    """ Premier événement reçu juste après la saisie de carte réussie par le client """
    try:
        # On re-récupère la session complète depuis l'API Stripe plutôt que de se fier
        # uniquement au payload du webhook, pour être sûr d'avoir toutes les infos à jour
        session_complete = stripe.checkout.Session.retrieve(session["id"])

        user_id = int(session_complete["metadata"].get("user_id"))
        plan_key = session_complete["metadata"].get("plan")
        customer_id = session_complete["customer"]
        subscription_id = session_complete["subscription"]

        current_app.logger.info(f"DEBUG - Traitement checkout pour user_id={user_id}, plan='{plan_key}'")

        try:
            validate_subscription_type(plan_key)
        except ValueError as e:
            current_app.logger.error(f"ERREUR - Plan invalide: {e}")
            return

        user = User.query.get(user_id)
        if not user:
            current_app.logger.error(f"Utilisateur {user_id} non trouvé")
            return

        current_app.logger.info(f"DEBUG - Utilisateur trouvé: {user.email}, subscription actuelle: '{user.subscription}'")

        try:
            price_id = PRICE_MAP.get(plan_key, "unknown")
            current_app.logger.info(f"DEBUG - Price ID: {price_id}")

            # Création de la ligne d'abonnement en BDD locale liée à l'historique de l'utilisateur
            new_subscription = Subscription(
                user_id=user_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                stripe_price_id=price_id,
                plan=plan_key,
                status='active',
                current_period_start=datetime.utcnow(),
                # current_period_end sera renseigné plus tard via l'événement
                # customer.subscription.updated (qui contient les vraies dates Stripe)
                current_period_end=None,
            )

            current_app.logger.info(f"DEBUG - Subscription créée avec plan='{new_subscription.plan}', status='{new_subscription.status}'")

            # On met à jour directement le rôle/niveau d'accès de l'utilisateur sur sa table principale
            # (en plus de la ligne Subscription dédiée à l'historique des paiements)
            old_subscription = user.subscription
            if plan_key in SUBSCRIPTION_TYPES:
                user.subscription = plan_key
                current_app.logger.info(f"DEBUG - User.subscription changé de '{old_subscription}' à '{user.subscription}'")
            else:
                raise ValueError(f"Type d'abonnement invalide pour ENUM: {plan_key}")

            db.session.add(new_subscription)
            # flush() envoie les changements à la base sans encore valider la transaction,
            # utile ici pour s'assurer que l'insertion ne lève pas d'erreur avant le commit final
            db.session.flush()
            db.session.commit()

            current_app.logger.info(f"DEBUG - Transaction commitée avec succès")

            # Relecture depuis la base après commit, uniquement pour vérifier/loguer
            # que les valeurs ont bien été persistées comme attendu (utile en debug)
            user_final = User.query.get(user_id)
            subscription_final = Subscription.query.filter_by(stripe_subscription_id=subscription_id).first()

            current_app.logger.info(f"SUCCESS - Abonnement créé pour utilisateur {user_id}")
            current_app.logger.info(f"SUCCESS - User.subscription final: '{user_final.subscription}'")
            current_app.logger.info(f"SUCCESS - Subscription.plan final: '{subscription_final.plan if subscription_final else 'None'}'")
            current_app.logger.info(f"SUCCESS - Subscription.status final: '{subscription_final.status if subscription_final else 'None'}'")

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"ERREUR transaction - Rollback effectué: {e}")
            raise

    except Exception as e:
        current_app.logger.error(f"ERREUR lors de la création de l'abonnement: {e}")
        current_app.logger.error(f"ERREUR - Type: {type(e)}")
        import traceback
        current_app.logger.error(f"ERREUR - Traceback: {traceback.format_exc()}")
        raise


def handle_payment_succeeded(invoice):
    """ Déclenché à chaque renouvellement mensuel réussi. On s'assure que l'accès reste 'active' """
    try:
        subscription_id = invoice["subscription"]
        if subscription_id:
            subscription_db = Subscription.query.filter_by(
                stripe_subscription_id=subscription_id
            ).first()

            if subscription_db:
                subscription_db.status = 'active'

                # Réapplique le plan sur l'utilisateur au cas où il aurait été rétrogradé
                # entre-temps (ex: après un échec de paiement précédent suivi d'un succès)
                user = User.query.get(subscription_db.user_id)
                if user and subscription_db.plan:
                    validate_subscription_type(subscription_db.plan)
                    user.update_subscription(subscription_db.plan, commit=False)

                db.session.commit()
                current_app.logger.info(f"Abonnement mis à jour: {subscription_id}")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur lors de la mise à jour du paiement: {e}")
        raise


def handle_subscription_updated(sub):
    """ Reçu si l'abonnement change de statut sur Stripe (par exemple s'il passe en impayé, ou si les dates de période changent) """
    try:
        stripe_sub_id = sub.get('id')
        if not stripe_sub_id:
            current_app.logger.error('handle_subscription_updated: id manquant dans le payload')
            return

        subscription_db = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
        if not subscription_db:
            # Peut arriver si l'abonnement a été créé hors de ce flux (ex: directement
            # dans le dashboard Stripe) ou si l'événement checkout.session.completed
            # n'a pas encore été traité au moment où celui-ci arrive
            current_app.logger.info(f"Subscription {stripe_sub_id} non trouvée en base")
            return

        status = sub.get('status')
        current_period_start = sub.get('current_period_start')
        current_period_end = sub.get('current_period_end')

        if status:
            try:
                validate_subscription_status(status)
                subscription_db.status = status
            except ValueError:
                # Stripe a beaucoup plus de statuts possibles (trialing, past_due, unpaid...)
                # que notre ENUM local (active/canceled) : on ignore simplement les statuts
                # non gérés plutôt que de faire échouer tout le traitement du webhook
                current_app.logger.warning(f"Statut inconnu reçu: {status}")

        # Conversion des timestamps UNIX envoyés par Stripe en objets datetime Python
        try:
            if current_period_start:
                subscription_db.current_period_start = datetime.utcfromtimestamp(int(current_period_start))
            if current_period_end:
                subscription_db.current_period_end = datetime.utcfromtimestamp(int(current_period_end))
        except Exception:
            # Erreur de conversion silencieusement ignorée : on préfère garder les anciennes
            # dates plutôt que de faire échouer toute la mise à jour pour ce détail
            pass

        # Réapplique le plan sur l'utilisateur (utile par exemple si le statut redevient 'active'
        # après une période de problème de paiement)
        user = User.query.get(subscription_db.user_id)
        if user and subscription_db.plan:
            try:
                validate_subscription_type(subscription_db.plan)
                user.update_subscription(subscription_db.plan, commit=False)
            except ValueError:
                current_app.logger.warning(f"Plan inconnu en base pour subscription {stripe_sub_id}: {subscription_db.plan}")

        db.session.commit()
        current_app.logger.info(f"Subscription {stripe_sub_id} mise à jour en base")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur handle_subscription_updated: {e}")
        raise


def handle_subscription_deleted(sub):
    """ Événement critique reçu quand l'abonnement expire définitivement ou est coupé côté Stripe. On repasse le user en gratuit """
    try:
        stripe_sub_id = sub.get('id')
        if not stripe_sub_id:
            current_app.logger.error('handle_subscription_deleted: id manquant dans le payload')
            return

        subscription_db = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
        if not subscription_db:
            current_app.logger.info(f"Subscription {stripe_sub_id} non trouvée en base lors d'une suppression")
            return

        subscription_db.status = 'canceled'
        subscription_db.current_period_end = datetime.utcnow()

        user = User.query.get(subscription_db.user_id)
        if user:
            old = user.subscription
            user.subscription = 'free'
            current_app.logger.info(f"Utilisateur {user.id} passé de '{old}' à 'free' suite à suppression Stripe")

        db.session.commit()
        current_app.logger.info(f"Subscription {stripe_sub_id} marquée annulée en base")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur handle_subscription_deleted: {e}")
        raise


# ============================================================
# Route : récupère l'état de l'abonnement actif d'un utilisateur
# Utilisé par le frontend pour afficher le plan en cours sur la page profil/paramètres
# ============================================================
@subscriptions_bp.route('/api/user/<int:user_id>/subscription', methods=['GET'])
def get_user_subscription(user_id):
    """ Endpoint pour permettre au front d'afficher l'état de l'abonnement sur l'interface profil / paramètres """
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404

        subscription = Subscription.query.filter_by(
            user_id=user_id,
            status='active'
        ).first()

        return jsonify({
            'subscription': subscription.to_dict() if subscription else None,
            'plan': user.subscription_level
        }), 200

    except Exception as e:
        current_app.logger.error(f"Erreur lors de la récupération de l'abonnement: {e}")
        return jsonify({'error': 'Erreur interne'}), 500


# ============================================================
# Route : annulation d'un abonnement par l'utilisateur lui-même
#
# Pas de vérification ici que l'appelant est bien l'utilisateur user_id
# (ou un admin) : n'importe qui connaissant l'URL pourrait potentiellement
# annuler l'abonnement d'un autre utilisateur. À sécuriser via une vérification
# de session/JWT correspondant à user_id.
#
# Effet immédiat (pas de "fin de période payée") : contrairement à une
# pratique courante chez Stripe (annuler à la fin de la période déjà payée),
# ici l'utilisateur perd l'accès premium tout de suite, même s'il a déjà payé
# pour le mois en cours. Dépend du choix produit voulu, mais c'est un point
# à confirmer.
# ============================================================
@subscriptions_bp.route('/api/user/<int:user_id>/cancel-subscription', methods=['POST'])
def cancel_subscription(user_id):
    """ Permet à un utilisateur de couper son abonnement lui-même depuis son espace client (effet immédiat ici) """
    try:
        subscription = Subscription.query.filter_by(
            user_id=user_id,
            status='active'
        ).first()

        if not subscription:
            return jsonify({'error': 'Aucun abonnement actif trouvé'}), 404

        current_app.logger.info(f"DEBUG - Annulation de l'abonnement {subscription.stripe_subscription_id} pour l'utilisateur {user_id}")

        # Demande d'arrêt envoyée directement à l'API Stripe (annulation immédiate côté Stripe aussi,
        # par défaut stripe.Subscription.cancel() ne fait pas de prorata/remboursement automatique)
        try:
            canceled_subscription = stripe.Subscription.cancel(subscription.stripe_subscription_id)
            current_app.logger.info(f"DEBUG - Abonnement Stripe annulé: {canceled_subscription.status}")
        except Exception as stripe_error:
            current_app.logger.error(f"ERREUR Stripe lors de l'annulation: {stripe_error}")
            return jsonify({'error': 'Erreur lors de l\'annulation sur Stripe'}), 500

        current_time = datetime.utcnow()
        subscription.status = 'canceled'
        subscription.current_period_end = current_time

        # On le rétrograde immédiatement en 'free' côté BDD locale
        # Note : ce changement est fait ici directement, en plus du webhook
        # customer.subscription.deleted qui sera aussi déclenché par Stripe suite à cet
        # appel — il y a donc une mise à jour "en double" (une fois ici de façon
        # synchrone, une fois via le webhook de façon asynchrone), ce qui est redondant
        # mais pas dangereux puisque les deux convergent vers le même état final
        user = User.query.get(user_id)
        if user:
            old_subscription = user.subscription
            validate_subscription_type('free')
            user.subscription = 'free'
            current_app.logger.info(f"DEBUG - Utilisateur {user_id} passé de '{old_subscription}' à 'free'")

        db.session.commit()

        current_app.logger.info(f"SUCCESS - Abonnement annulé immédiatement pour l'utilisateur {user_id} à {current_time}")

        return jsonify({
            'message': 'Abonnement résilié immédiatement avec succès',
            'status': 'canceled',
            'new_plan': 'free',
            'canceled_at': current_time.isoformat()
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erreur lors de l'annulation: {e}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Erreur lors de l\'annulation'}), 500