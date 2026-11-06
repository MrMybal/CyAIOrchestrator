---
id: viewer-3d
title: 3D viewer & PBR
description: Inspect geometry, backgrounds, lighting and materials.
section: Files, media & integrations
parent: files
order: 14
revision: 1
---


1. Click a supported GLB/glTF, OBJ, STL or PLY attachment or local link.
2. Drag to orbit, wheel to zoom and right-drag to pan. Recenter fits the model; Wireframe exposes topology.
3. Choose a dark, grey, white, midnight blue or studio background. Compare Studio PBR, Soft, Contrast and Daylight lighting.
4. Adjust exposure and light rotation. Use Open with Windows or File Explorer for another application.

Embedded GLB/glTF textures and supported PBR materials are preserved with studio environment lighting. Self-contained GLB is the most convenient preview format. OBJ is loaded as geometry only: companion MTL materials are not loaded. STL/PLY use the viewer’s material and available vertex colours. External glTF resources may not be accessible through the attachment.

```callout
{"type": "info", "title": "Keep in mind", "body": "Preview controls do not rewrite the asset. The viewer is for inspection, not full modelling or conversion. Missing textures or unsupported extensions may require the authoring application."}
```


## Related chapters {#related}

- [Attachments, images & video](doc:files)
- [CyAnnota visual annotations](doc:cyannota)
- [Plugins & CyTools](doc:extensions)
