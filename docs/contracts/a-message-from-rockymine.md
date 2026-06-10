Hey Opus, I wanted to inform you about a couple of features that are currently missing from implementation and that need consolidation beforehand. Some of these are touching literal feature gaps but most are data model related and belong as actual tasks inside step B and need clarification with me and the codebase. Some are also additional A tickets. They shall prioritized and added to the correct phase of the refactor-plan. They shall be written up cleanly like the other tasks.

## 1. Features, Oversights, and Validation

# Undo/Redo

A real editor needs undo and redo support of user actions. within this project we need to decide the right model that can be applied. pure redo and undo of create and delete might not be enough and fitting given how for a wool you could delete the monument which still keeps the wool but deletes the monument. i think that is PATCH call right now. 

# Symmetry Axis and Center Point

We must differentiate more cleanly between they type of center point setup. a maps center can fall into a 2x2, 1x2, 2x1 and 1x1.

You pointed out that some four team maps are actually rotated like diagonally (45°). we need to support changing the axis angles for the user inside the sketch tool so that the rotation axis can also go diagonally through x and z (and potentially in the detection code too, although those maps will just appear as normal rot 90 maps regardless of whether the builder uses a diagonal axis, right? both produce the same kind of symmetry).

# Filters, Regions and their Relation

Concept / routes are needed to build the filter and region relations. We should use `docs/filter-use-cases.md` as starting point but extend the picture across the now full dataset of maps. In `docs/requirements/editor-filters.md` we have an **outdated** document. The main importance is that users need to be able to manually add the filters to regions/unions but the tool should also **suggest filters / question the user** based on the setup of the map. at the bare minimum the positive build regions inside the build region step need to be wired with the correct filter (see `docs/requirements/editor-build-regions.md`). i could imagine the tool "asking" the user to auto-group the regions and then apply the filter automatically, also considering the layer_y0.parquet information. The second group of filters that needs to be supported in v1 are apply-enter rules. basically the most common filter usages found from the repo should be supported as "intelligent templates".

# Compatibility of Sketch Exports with Editor

Currently exported sketches cannot always be displayed inside the editor. the canvases show "Loading map..." and "No segment data". this likely has to to with the required layer_*.parquet files not being available after export. 

# Performance and implementation drift of sketch and editor canvas with regards to shape creation

The sketch tool feels silky smooth while editing given it edits in-memory data while the editor always "asks" the json for validation. how can we align those performance concerns related with data-handling of geometry objects? Are the two tools already using a shared geometry format?

# Wool existence validation

A map will not work when no wool is obtainable in the map. wools can be obtained in many maps. See `Sub-step 3: Wool Availability Check` in `docs/requirements/editor-objectives.md`. Important reminder: PGM spawner and renewable / block drop needs to be configurable.

# Validation Model while editing

We need to prevent "dumb" user errors like adding a monument when no team or wool is defined yet, i.e. wool needs to exist before a monument can be defined, team needs to exist before a wool can be defined, a map needs at least 2 teams (rotate 90 needs 4 teams, mirror can also support more than 2 teams in creative edge-case layouts, e.g. ruedigers_pentawool).

# Intelligent ID and color defaults

right now teams are added as ID "new-team-n" and Name "New Team" with Chat Color = Blue. SImilar to wools they should just be added as new colors that do not exist yet, we can only theoretically support a 16 team map given the color limit of minecraft. IDs and names should be like `<color>-team` and `<Color> Team`. realistically the cap should be 8 though (i think your one query revealed 8 is the max anyways).

# working off of xml templates

Ruediger_LP is writing many maps and has actually a template for it I added inside: `docs/xml_template.xml`. Instead starting from the blank the tool could *optionally* take off some mental load from the user and ask the user on import / load how many teams / wools this map has. or just find the best option from symmetry and *.parquet files. then editing becomes more directed.

# sketches are currently not promoted to 'maps' when the user exports them and opens them in the editor

potential design and data model oversight. need to differentiate between genuine maps and map sketches.

## 2. Stack selection

easy to install and maintain. the final tool should be hosted for others to access, the code needs to support that. the current usage vision is as follows. the Overcast Community server which runs and continues development of PGM has a 1.8.9 minecraft server that has a buildserver accessible with `/server mapmaker`. On this server everyone creates their maps. The server has a `//download` plugin that downloads the world, auto-prunes it (remove air chunks basically), zips it and sends you a temporary download link of the following format: https://occ-maps.s3.ca-central-1.amazonaws.com/rockymine?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Date=20260610T110121Z&X-Amz-SignedHeaders=host&X-Amz-Credential=AKIA5AB65A546FOQWUGQ%2F20260610%2Fca-central-1%2Fs3%2Faws4_request&X-Amz-Expires=120&X-Amz-Signature=c22aa331e6bad55c9064595d1bbe365a86c330978f5f9be24093496e923dde1a (by the time you read this, this link will have died as it only lives for a minute or so). I copied the zip into sf-repos/rockymine (48).zip. The current tool can import a map from a zip link like this already and will open allow opening it in the Editor. The final vision is to have a separate Java plugin where the user just types a command like `/map-studio` and the plugin downloads the map, sends it to a server and returns a link where the user can define the map.xml. Importantly I do not want this tool to be collaborative, editing of the same files at once should not be possible. If users were to open the same map they'd be in different sessions not influencing their data. Given only one person realistically always writes an xml anyways this is an edge case but should be accounted for. The sketch -> editor workflow stays separate and available. 

## 3. Routes concern

We should make sure that the routes for updating, adding, deleting data are set up nicely and consistently so that new features can easily be added. requires validation of current routes.

## 4. part 3d / 2.5d support

build region activity already utilizes layer_segments-parquet to render a depth-side-on view of a map to select the maximum build height with a slider. within the editor it is impossible to properly position point, block (e.g. monuments) and cuboid coordinates right now. perhaps we can utilize this segments view and render a 3d view for a selection. or go deeper with the //map-studio plugin integration to directly send some coordinates based on the worldedit want into the tool. either way some support is needed.