# PARTIE 1 — Questions et réponses

## 1. 

 Deux clients réservent la dernière place au même instant, l'un dans Daisy, l'autre chez le partenaire. Décris précisément ce qui se passe dans ton implémentation. Si ton système peut surréserver, dis-le et explique dans quelles conditions.

**Réponse :** Pour cet exercice, je suppose qu'Artisia doit d'abord demander à Daisy les places correspondantes et réussir à les verrouiller avant de confirmer une réservation. Dans ce cas, il est théoriquement possible de garantir strictement l'absence de surréservation.

En revanche, si Artisia utilise un stock indépendant sans vérifier auprès de Daisy, c'est-à-dire sans source de vérité (SoT), une seule des deux plateformes peut obtenir la dernière place, mais les deux affichent une réservation réussie, ce qui entraîne une surréservation. Par exemple, lorsque l'événement `booking.created` est transmis à Daisy, le worker tente de traiter l'événement webhook, constate qu'il n'y a plus de place et finit par renvoyer une erreur `409`. Mon code n'intercepte pas cette exception. Le statut de cet événement webhook reste donc `pending`, alors que les réservations sont affichées comme confirmées des deux côtés.

## 2. 
 Le partenaire est injoignable pendant 20 minutes. Que voit l'artisan pendant ce temps ? Et au retour du service, comment rattrapes-tu l'écart ?

**Réponse :** Grâce au pattern Outbox, si l'API Artisia est inaccessible, nos tâches de synchronisation s'accumulent dans la table des événements Outbox. La synchronisation peut reprendre une fois l'API Artisia de nouveau disponible.

## 3. 
Le même webhook arrive trois fois. Comment tu t'en protèges, et à quel coût ?

**Réponse :** Tout d'abord, dans la table des événements webhook, nous avons une clé primaire unique composée de `partner_id` et de `event_id`, qui garantit l'unicité de chaque webhook. Ainsi, même si le même webhook arrive trois fois, un seul est enregistré dans cette table et un seul est finalement traité.

De plus, dans la table des réservations, nous avons une clé unique composée de `source` et de `source_ref`, qui garantit également l'unicité de chaque réservation. Même si tous les doublons sont déjà traités au niveau des webhooks, j'ai tout de même conservé la logique de déduplication des réservations. Le coût actuel est de devoir maintenir ces données et conserver le payload des événements.

## 4. 
Tu dois choisir entre « ne jamais surréserver » et « ne jamais bloquer une vente ». Tu choisis quoi, et qu'est-ce que tu dis à l'artisan qui subit l'autre côté du compromis ?

**Réponse :** Dans un contexte de développement réel, je préférerais vendre moins plutôt que de surréserver. Je pense que le coût d'une surréservation est supérieur à celui d'une vente manquée. Je l'expliquerais ainsi : lorsque la plateforme partenaire est inaccessible, nous ne pouvons pas garantir que le nombre de places restantes affiché par le système correspond toujours à la disponibilité réelle. Dans cette situation, nous préférons suspendre temporairement les réservations concernées plutôt que de risquer de vendre deux fois la même place.

# PARTIE 2 — Socle commun

## 1. Mon journal de bord

**Temps consacré : 7 heures**

Je n'avais jamais travaillé sur un produit similaire auparavant, mais je pense que réserver un créneau et acheter un produit reposent fondamentalement sur des principes similaires : dans les deux cas, il y a un paiement et un stock à gérer. J'ai donc d'abord pensé aux grandes plateformes d'e-commerce, comme Ticketmaster et Shopify. En suivant cette idée, j'ai lu deux articles de Shopify et d'AWS sur la gestion de la cohérence des stocks.

J'ai utilisé Python et FastAPI, des technologies que je connais bien, avec PostgreSQL comme base de données. Comme ce sujet ne nécessite pas de frontend, j'ai développé uniquement le backend.

J'ai commencé par analyser les limitations de l'API Artisia et identifier les principaux risques techniques, notamment les surréservations, les webhooks dupliqués et les échecs de synchronisation. À partir de ces problèmes, j'ai conçu le modèle de données, puis j'ai commencé à développer les API côté Daisy en utilisant le pattern Outbox, ainsi que les flux de synchronisation bidirectionnelle des réservations.

La principale difficulté a été de maintenir la cohérence des disponibilités entre deux systèmes capables de confirmer des réservations indépendamment. En raison des limitations de l'API Artisia, il n'est pas possible de réaliser une transaction atomique entre les deux plateformes. Il est donc impossible de garantir complètement une cohérence forte des réservations entre elles.

Compte tenu du temps limité, j'ai fait les hypothèses et les choix suivants : je ne prends en compte que la création de nouvelles réservations, sans gérer les annulations ou les autres opérations, et je ne considère qu'un seul partenaire, Artisia. J'ai également supposé qu'Artisia vérifierait d'abord auprès de Daisy la disponibilité réelle des places avant de confirmer une réservation, et qu'Artisia serait capable de gérer correctement un refus du webhook. **Ce comportement n'a cependant pas été implémenté dans le mock.**

J'ai choisi de considérer Daisy comme la **Source of Truth (SoT)**, afin de limiter autant que possible les risques de surréservation. Actuellement, la base de données Daisy peut empêcher les surréservations de son propre côté, mais elle ne peut pas garantir l'absence de surréservation entre Daisy et Artisia.

Il s'agit fondamentalement d'un problème de concurrence dans un système distribué. Avec les API Artisia fournies dans l'énoncé, il n'existe aucun moyen de garantir absolument l'absence de surréservation sans répartir les quotas entre les plateformes. Cependant, une telle répartition pourrait aller à l'encontre de l'exigence de synchronisation des disponibilités entre les deux plateformes. Compte tenu du temps disponible, je n'ai donc pas retenu la solution de répartition des quotas.

## 2. Mon classement des tickets

Du ticket qui m'intéresse le plus à celui qui m'intéresse le moins :

1. **Ticket 6** — Concevoir une API publique pour permettre aux futurs partenaires de s'intégrer de manière autonome.
2. **Ticket 2** — Optimiser les performances du calendrier du back-office.
3. **Ticket 1** — Corriger une intégration partenaire qui ne fonctionne plus.
4. **Ticket 8** — Mettre en place un design system unifié.
5. **Ticket 3** — Intégrer les paiements sur place par TPE.
6. **Ticket 4** — Ajouter un filtre par type de cours dans la liste des réservations.
7. **Ticket 5** — Analyser le taux d'abandon du widget de réservation.
8. **Ticket 7** — Investiguer les écarts entre les exports comptables et les relevés bancaires.

## 3. Mes deux premières semaines chez Daisy

### Première semaine

Je commencerais par échanger avec les deux autres développeurs de l'équipe afin de comprendre le métier, l'architecture actuelle du système, les conventions de code ainsi que les parties du projet dont je serai responsable.

Je me concentrerais principalement sur la structure des données et je suivrais un flux de données complet à travers le système, par exemple depuis le clic d'un utilisateur sur le frontend jusqu'aux opérations effectuées dans la base de données.

### Deuxième semaine

J'essaierais de réaliser une petite API ou d'implémenter une fonction simple, tout en m'adaptant progressivement à l'environnement et au rythme de travail de l'équipe.

Mon objectif serait de livrer une première contribution fiable tout en me familiarisant rapidement avec la base de code existante et en développant progressivement mon autonomie.

## 4. Ce que j'aurais aimé demander à Daisy

**Question technique**

Les réservations effectuées directement sur Artisia sont-elles définitivement confirmées avant l'envoi du webhook `booking.created`, ou Daisy intervient-il dans leur processus de validation ?

**Hypothèse retenue**

J'ai supposé qu'Artisia vérifierait d'abord auprès de Daisy la disponibilité réelle des places avant de confirmer une réservation, et qu'Artisia serait capable de gérer correctement un refus du webhook.

Sur la base de cette hypothèse, j'ai choisi de mettre en place un mécanisme de synchronisation bidirectionnelle et de détection des conflits, tout en distinguant clairement la cohérence des données que PostgreSQL peut garantir au sein de Daisy des limites de cohérence forte entre deux plateformes indépendantes.
