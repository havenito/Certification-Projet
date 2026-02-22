# Évaluation Cloud On-Premise - École Heptagone

## 1. Contexte et Besoins

L'école Heptagone souhaite héberger une infrastructure pour ses cours DevOps et Cloud. Le besoin est d'accueillir **2 classes de 20 étudiants simultanément** (40 étudiants), chacun déployant 4 instances Debian.

### 1.1 Configuration par Étudiant

| Instance | RAM | CPU | Stockage (estimé) |
|----------|-----|-----|-------------------|
| Bastion | 512 MiB | 1 vCPU | 10 GB |
| NGINX (reverse proxy) | 1 GiB | 1 vCPU | 10 GB |
| Apache+PHP+MariaDB #1 | 2 GiB | 2 vCPU | 20 GB |
| Apache+PHP+MariaDB #2 | 2 GiB | 2 vCPU | 20 GB |
| **Total par étudiant** | **5.5 GiB** | **6 vCPU** | **60 GB** |

### 1.2 Besoins Totaux pour 40 Étudiants

- **RAM totale** : 40 × 5.5 GiB = **220 GiB** (+ 10% overhead = **242 GiB**)
- **vCPU totaux** : 40 × 6 = **240 vCPU**
- **Stockage** : 40 × 60 GB = **2.4 TB** (+ 20% pour Proxmox/système = **3 TB**)

## 2. Solution On-Premise avec Proxmox

### 2.1 Configuration Matérielle Requise

Pour assurer redondance et performances, nous recommandons un **cluster de 3 nœuds Proxmox** :

#### Spécifications par Serveur
- **CPU** : 2× Intel Xeon Silver 4314 (16 cores/32 threads chacun) = 64 threads
- **RAM** : 256 GB DDR4 ECC
- **Stockage** : 2× SSD NVMe 2TB (RAID 1) + 4× SSD SATA 2TB (stockage Ceph)
- **Réseau** : 2× 10GbE pour réseau Ceph + 2× 1GbE pour management
- **Alimentation** : Double alimentation redondante

#### Cluster Total
- **CPU** : 192 threads (ratio 1:1.25 confortable)
- **RAM** : 768 GB (3× overhead)
- **Stockage** : Pool Ceph ~12 TB utilisables (réplication ×2)

### 2.2 Coûts On-Premise

| Élément | Quantité | Prix Unitaire | Total |
|---------|----------|---------------|-------|
| Serveur Dell PowerEdge R650 (configuré) | 3 | 8 500 € | 25 500 € |
| Switch 10GbE (48 ports) | 1 | 3 000 € | 3 000 € |
| Onduleur 3000VA | 2 | 800 € | 1 600 € |
| Rack 42U avec climatisation | 1 | 2 500 € | 2 500 € |
| Câblage et accessoires | - | 500 € | 500 € |
| **CAPEX Total** | | | **33 100 €** |

#### Coûts Opérationnels Annuels (OPEX)

| Élément | Coût Annuel |
|---------|-------------|
| Électricité (~3.5 kW × 24/7 × 0.20 €/kWh) | 6 132 € |
| Climatisation (50% de la conso électrique) | 3 066 € |
| Bande passante Internet (1 Gbps pro) | 1 200 € |
| Maintenance/Support | 2 000 € |
| **OPEX Total/an** | **12 398 €** |

**Coût Total sur 5 ans** : 33 100 € + (12 398 € × 5) = **95 090 €**  
**Coût par étudiant/an** : 95 090 € ÷ 5 ÷ 40 = **~475 €/étudiant/an**

## 3. Solution OVH Serveurs Dédiés

### 3.1 Configuration Serveurs OVH

**Serveur recommandé** : OVH Rise-4  
- Intel Xeon-E 2386G (6c/12t)
- 128 GB RAM DDR4 ECC
- 2× NVMe 960 GB (Soft RAID)
- Bande passante 1 Gbps unmetered

**Nombre requis** : 3 serveurs pour redondance (comme on-premise)

### 3.2 Coûts OVH

| Élément | Prix Mensuel | Prix Annuel |
|---------|--------------|-------------|
| 3× Rise-4 @ 209 €/mois | 627 € | 7 524 € |
| vRack (réseau privé) | Gratuit | 0 € |
| Licences Proxmox (Community) | Gratuit | 0 € |
| **Total/an** | | **7 524 €** |

**Coût Total sur 5 ans** : 7 524 € × 5 = **37 620 €**  
**Coût par étudiant/an** : 37 620 € ÷ 5 ÷ 40 = **~188 €/étudiant/an**

## 4. Comparaison et Recommandations

| Critère | On-Premise | OVH Dédié |
|---------|------------|-----------|
| Coût initial | 33 100 € | 0 € |
| Coût 5 ans | 95 090 € | 37 620 € |
| **Économie OVH** | - | **60% moins cher** |
| Contrôle matériel | Total | Limité |
| Scalabilité | Difficile | Facile (ajout serveurs) |
| Maintenance | École | OVH (hardware) |
| Latence | Minimale | <5ms (datacentre français) |

### Recommandation

**OVH est recommandé** pour un premier déploiement (économie de ~57k€ sur 5 ans, pas de CAPEX, maintenance simplifiée). L'on-premise devient intéressant à partir de 100+ étudiants simultanés ou pour des besoins très spécifiques (données sensibles, latence critique).

## 5. BONUS : Alternatives à Proxmox

### 5.1 Solutions Open Source Comparables

| Solution | Avantages | Inconvénients | Recommandation École |
|----------|-----------|---------------|----------------------|
| **OpenStack** | Standard industrie, très complet, extensible | Complexe à installer/maintenir, ressources importantes | ⚠️ Trop complexe sauf si cours OpenStack |
| **Apache CloudStack** | Plus simple qu'OpenStack, interface Web intuitive | Communauté plus petite | ✅ Alternative viable |
| **XCP-ng + Xen Orchestra** | Basé sur Xen/Citrix, performant, gratuit | Moins populaire, moins de documentation | ✅ Bon compromis |
| **oVirt** | Basé sur KVM (comme Proxmox), par Red Hat | Interface moins moderne | ⚠️ Moins convivial |
| **Harvester** | Moderne, Kubernetes natif, hyperconvergé | Jeune (2020), moins stable | ⚠️ Trop récent pour production |
| **LXD/Incus** | Léger, conteneurs système, simple | Containers uniquement (pas de VMs complètes) | ⚠️ Limité pour la diversité |

### 5.2 Notre Top 3 pour Heptagone

1. **Proxmox VE** (recommandé) : Communauté large, documentation excellente, stack LXC+KVM, interface intuitive
2. **XCP-ng + Xen Orchestra** : Bon pour enseigner concepts Citrix/Xen
3. **Apache CloudStack** : Si besoin d'enseigner gestion cloud multi-tenant

### 5.3 Pourquoi pas OpenStack ?

OpenStack est le standard industrie, **mais** :
- Déploiement minimal : 3-5 nœuds de contrôle + 3+ compute
- Nécessite expertise DevOps avancée
- Overhead important (~30% des ressources pour le control plane)

**Recommandation** : OpenStack uniquement si vous proposez un cours spécifique OpenStack, sinon Proxmox suffit amplement.

## 6. Conclusion

- **Solution recommandée** : Démarrer avec **3 serveurs OVH Rise-4** sous **Proxmox VE**
- **Coût** : 7 524 €/an (~188 €/étudiant/an)
- **Scalabilité** : Ajouter des nœuds selon croissance
- **Migration** : Possibilité de migrer on-premise plus tard si justifié

Ce setup permet de former 40 étudiants simultanément avec une infrastructure professionnelle, résiliente et économique.
