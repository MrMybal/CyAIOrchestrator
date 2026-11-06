---
id: viewer-3d
title: Vue 3D et PBR
description: Inspecter géométrie, fonds, éclairages et matériaux.
section: Fichiers, médias et intégrations
parent: files
order: 14
revision: 1
sourceRevision: 1
---


1. Cliquez sur une pièce jointe ou un lien GLB/glTF, OBJ, STL ou PLY.
2. Glissez pour tourner, utilisez la molette pour zoomer et le clic droit pour déplacer. Recentrer recadre ; Filaire montre la topologie.
3. Choisissez fond sombre, gris, blanc, bleu nuit ou studio. Comparez Studio PBR, Doux, Contrasté et Lumière du jour.
4. Réglez exposition et rotation de lumière. Ouvrir avec Windows et Explorateur donnent accès à un autre logiciel.

Textures intégrées GLB/glTF et matériaux PBR pris en charge sont conservés avec un éclairage d’environnement. Un GLB autonome facilite l’aperçu. OBJ est chargé en géométrie seule : les matériaux MTL associés ne sont pas chargés. STL/PLY utilisent le matériau du visualiseur et les couleurs de sommets disponibles. Les ressources externes glTF peuvent être inaccessibles.

```callout
{"type": "info", "title": "À retenir", "body": "Les commandes d’aperçu ne réécrivent pas le fichier. Cette vue sert à l’inspection, pas à la modélisation complète. Textures absentes ou extensions non gérées peuvent nécessiter le logiciel d’origine."}
```


## Chapitres associés {#related}

- [Pièces jointes, images et vidéos](doc:files)
- [Annotations visuelles CyAnnota](doc:cyannota)
- [Plugins et CyTools](doc:extensions)
