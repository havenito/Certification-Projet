"use client";

import React, { useState, useEffect } from 'react';
import Card from '../../../components/Main/Premium/Card';
import CancelSubscriptionModal from '../../../components/Main/Premium/CancelSubscriptionModal';
import SubscriptionNotification from '../../../components/Main/Premium/SubscriptionNotification';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link'; 
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'; 
import { faArrowLeft, faTrash } from '@fortawesome/free-solid-svg-icons'; 
import { useSession } from 'next-auth/react';

const subscriptionPlans = [
  {
    id: 'free',
    name: 'Minouverse Free',
    description: 'Les fonctionnalités de base pour commencer.',
    price: '0€',
    features: [
        'Accès au fil d\'actualité',
        'Poster des "Miaous"',
        'Suivre d\'autres utilisateurs',
        'Messagerie directe',
    ],
  },
  {
    id: 'plus',
    name: 'Minouverse Plus',
    description: 'Plus de fonctionnalités pour une meilleure expérience.',
    price: '4.99€',
    features: [
      'Tout de Minouverse Free',
      'Badge "Plus" sur le profil',
      'Photo de profil et bannière animées',
    ],
  },
  {
    id: 'premium',
    name: 'Minouverse Premium ✨',
    description: 'Le meilleur de Minouverse pour les membres qui veulent se démarquer.',
    price: '9.99€',
    features: [
      'Tout de Minouverse Plus',
      'Badge "Premium" exclusif et prioritaire',
      'Accès anticipé aux nouveautés Premium',
      'Choix de thèmes personnalisés (à venir)',
    ],
  },
];

export default function PremiumPage() {
  const [selectedPlanId, setSelectedPlanId] = useState(null);
  const [currentPlanId, setCurrentPlanId] = useState('free');
  const [loading, setLoading] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [userSubscription, setUserSubscription] = useState(null);
  const [notification, setNotification] = useState(null);
  const { data: session, update } = useSession();

  useEffect(() => {
    if (session?.user) {
      console.group('💎 INFORMATIONS UTILISATEUR - PAGE PREMIUM');
      console.log('📧 Email:', session.user.email);
      console.log('👤 ID:', session.user.id);
      console.log('🏷️ Pseudo:', session.user.pseudo);
      console.log('💰 Abonnement actuel:', session.user.subscription);
      console.log('💳 Type d\'abonnement détecté:', currentPlanId);
      console.log('🔍 Session complète:', session);
      console.groupEnd();
    }
  }, [session, currentPlanId]);

  const fetchUserSubscription = async () => {
    if (session?.user?.id) {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_FLASK_API_URL}/api/user/${session.user.id}/subscription`);
        const data = await response.json();
        
        setCurrentPlanId(data.plan || 'free');
        setUserSubscription(data.subscription);
        
        console.log('Données d\'abonnement récupérées:', data);
      } catch (error) {
        console.error('Erreur lors de la récupération de l\'abonnement:', error);
        setCurrentPlanId('free');
      }
    }
  };

  useEffect(() => {
    // Récupérer l'abonnement actuel de l'utilisateur
    if (session?.user?.subscription) {
      setCurrentPlanId(session.user.subscription);
    }

    fetchUserSubscription();
  }, [session]);

  // Gérer les paramètres de retour de Stripe
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const success = urlParams.get('success');
    const canceled = urlParams.get('canceled');

    if (success) {
      setNotification({
        type: 'success',
        message: 'Paiement réussi ! Votre abonnement a été activé.',
        details: 'Vous avez maintenant accès à toutes les fonctionnalités premium.'
      });
      
      const newUrl = window.location.pathname;
      window.history.replaceState({}, document.title, newUrl);
      
      const updateSession = async () => {
        try {
          const response = await fetch(`${process.env.NEXT_PUBLIC_FLASK_API_URL}/api/user/${session.user.id}/subscription`);
          const data = await response.json();
          
          await update({
            subscription: data.plan || 'free'
          });
          
          setCurrentPlanId(data.plan || 'free');
          setUserSubscription(data.subscription);
          console.log('Session mise à jour avec le nouvel abonnement:', data.plan);
        } catch (error) {
          console.error('Erreur lors de la mise à jour de la session:', error);
        }
      };

      if (session?.user?.id) {
        updateSession();
      }
    } else if (canceled) {
      setNotification({
        type: 'info',
        message: 'Paiement annulé.',
        details: 'Aucun changement n\'a été effectué sur votre abonnement.'
      });
      
      const newUrl = window.location.pathname;
      window.history.replaceState({}, document.title, newUrl);
    }
  }, [session?.user?.id, update]);

  const handleCardClick = (planId) => {
    setSelectedPlanId(planId === selectedPlanId ? null : planId);
  };

  const handleSubscribe = async (planId) => {
    if (!session?.user?.id) {
      setNotification({
        type: 'error',
        message: 'Vous devez être connecté pour vous abonner',
        details: 'Veuillez vous connecter et réessayer.'
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_FLASK_API_URL}/api/create-checkout-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          planId: planId,
          userId: session.user.id
        }),
      });

      const data = await response.json();

      if (response.ok) {
        window.location.href = data.url;
      } else {
        setNotification({
          type: 'error',
          message: 'Erreur lors de la création de la session de paiement',
          details: data.error || 'Une erreur inattendue s\'est produite.'
        });
      }
    } catch (error) {
      console.error('Erreur:', error);
      setNotification({
        type: 'error',
        message: 'Erreur lors de la création de la session de paiement',
        details: 'Veuillez vérifier votre connexion internet et réessayer.'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCancelSubscription = () => {
    setShowCancelModal(true);
  };

  const confirmCancelSubscription = async () => {
    if (!session?.user?.id) {
      setNotification({
        type: 'error',
        message: 'Vous devez être connecté pour annuler votre abonnement',
        details: 'Veuillez vous reconnecter et réessayer.'
      });
      return;
    }

    setCancelLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_FLASK_API_URL}/api/user/${session.user.id}/cancel-subscription`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (response.ok) {
        setNotification({
          type: 'success',
          message: 'Votre abonnement a été résilié immédiatement.',
          details: 'Vous êtes maintenant sur le plan gratuit. Vous pouvez souscrire à nouveau à tout moment.'
        });
        
        // Mettre à jour la session et les états locaux
        await update({
          subscription: 'free'
        });
        
        setCurrentPlanId('free');
        setUserSubscription(null);
        setShowCancelModal(false);
        
        // Recharger les données d'abonnement
        await fetchUserSubscription();
        
        console.log('Abonnement annulé avec succès');
      } else {
        setNotification({
          type: 'error',
          message: 'Erreur lors de l\'annulation de l\'abonnement',
          details: data.error || 'Une erreur inattendue s\'est produite.'
        });
      }
    } catch (error) {
      console.error('Erreur:', error);
      setNotification({
        type: 'error',
        message: 'Erreur lors de l\'annulation de l\'abonnement',
        details: 'Veuillez vérifier votre connexion internet et réessayer.'
      });
    } finally {
      setCancelLoading(false);
    }
  };

  const cancelModal = () => {
    setShowCancelModal(false);
  };

  const hasActiveSubscription = currentPlanId !== 'free';

  return (
    <div className="min-h-screen bg-[#1f1f1f] py-12 px-4 sm:px-6 lg:px-8 text-white w-full relative">
      {/* Notification */}
      {notification && (
        <SubscriptionNotification
          type={notification.type}
          message={notification.message}
          details={notification.details}
          isVisible={!!notification}
          onClose={() => setNotification(null)}
        />
      )}

      {loading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-40">
          <div className="bg-white p-6 rounded-lg">
            <p className="text-black">Redirection vers le paiement...</p>
          </div>
        </div>
      )}

      <Link href="/home" passHref>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="absolute top-4 left-4 sm:top-6 sm:left-6 lg:top-8 lg:left-8 flex items-center px-4 py-2 bg-[#333] text-white rounded-full shadow-md hover:bg-[#444] transition-colors duration-200"
        >
          <FontAwesomeIcon icon={faArrowLeft} className="mr-2 h-4 w-4" />
          Retour
        </motion.button>
      </Link>

      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center mb-12 pt-16"
      >
        <h1 className="text-4xl font-extrabold text-[#90EE90] mb-4">
          Choisissez votre abonnement Minouverse
        </h1>
        <p className="text-lg text-gray-400">
          Débloquez plus de fonctionnalités et soutenez la plateforme.
        </p>
        
        {hasActiveSubscription && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="mt-6"
          >
            <motion.button
              onClick={handleCancelSubscription}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="bg-red-600 hover:bg-red-700 text-white px-6 py-3 rounded-full font-semibold text-sm flex items-center mx-auto transition-all duration-200"
            >
              <FontAwesomeIcon icon={faTrash} className="mr-2" />
              Résilier mon abonnement
            </motion.button>
            <p className="text-sm text-gray-400 mt-4">
              Pour changer d'abonnement, vous devez d'abord résilier votre abonnement actuel.
            </p>
          </motion.div>
        )}
      </motion.div>

      <motion.div
        initial="hidden"
        animate="visible"
        variants={{
          visible: { transition: { staggerChildren: 0.1 } },
        }}
        className="grid grid-cols-1 md:grid-cols-3 gap-12 items-stretch max-w-6xl mx-auto"
      >
        {subscriptionPlans.map((plan) => (
          <motion.div
            key={plan.id}
            variants={{
              hidden: { opacity: 0, y: 20 },
              visible: { opacity: 1, y: 0 },
            }}
            className="flex"
          >
            <Card
              plan={plan}
              isSelected={selectedPlanId === plan.id}
              isCurrent={currentPlanId === plan.id}
              onClick={() => handleCardClick(plan.id)}
              onSubscribe={handleSubscribe}
              className="flex-1"
              isDisabled={hasActiveSubscription && plan.id !== 'free' && plan.id !== currentPlanId}
            />
          </motion.div>
        ))}
      </motion.div>

      <CancelSubscriptionModal
        isOpen={showCancelModal}
        onClose={cancelModal}
        onConfirm={confirmCancelSubscription}
        isLoading={cancelLoading}
        currentPlan={currentPlanId}
        subscriptionPlans={subscriptionPlans}
      />
    </div>
  );
}