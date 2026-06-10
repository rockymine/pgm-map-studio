# annealing_iv — region categorization (B5 fixture, VERIFIED 2026-06-10)

Verified test oracle for the multi-signal derivation. See docs/contracts/region-categorization.md.
Machine-readable copy: tests/fixtures/region_categories/annealing_iv.json

| region | type | category | roles |
|---|---|---|---|
| `blue-spawn-point` | cylinder | **spawn** | — |
| `red-spawn-point` | cylinder | **spawn** | — |
| `green-spawn-point` | cylinder | **spawn** | — |
| `yellow-spawn-point` | cylinder | **spawn** | — |
| `obs-spawn-point` | cylinder | **observer_spawn** | — |
| `blue-wool-spawn` | cuboid | **wool_spawner** | — |
| `red-wool-spawn` | cuboid | **wool_spawner** | — |
| `green-wool-spawn` | cuboid | **wool_spawner** | — |
| `yellow-wool-spawn` | cuboid | **wool_spawner** | — |
| `blue-spawn` | rectangle | **spawn** | enter=only-blue |
| `red-spawn` | rectangle | **spawn** | enter=only-red |
| `green-spawn` | rectangle | **spawn** | enter=only-green |
| `yellow-spawn` | rectangle | **spawn** | enter=only-yellow |
| `blue-team-red-wool` | block | **monument** | — |
| `blue-team-green-wool` | block | **monument** | — |
| `blue-team-yellow-wool` | block | **monument** | — |
| `red-team-green-wool` | block | **monument** | — |
| `red-team-yellow-wool` | block | **monument** | — |
| `red-team-blue-wool` | block | **monument** | — |
| `green-team-yellow-wool` | block | **monument** | — |
| `green-team-blue-wool` | block | **monument** | — |
| `green-team-red-wool` | block | **monument** | — |
| `yellow-team-blue-wool` | block | **monument** | — |
| `yellow-team-red-wool` | block | **monument** | — |
| `yellow-team-green-wool` | block | **monument** | — |
| `spawns` | union | **spawn** | block_break=only-iron, block_place=only-iron-cause-world |
| `not-spawns` | negative | **other** | rule_container |
| `blues-woolroom` | union | **wool_room** | block=blues-woolrooms-filter, enter=not-blue |
| `reds-woolroom` | union | **wool_room** | block=reds-woolrooms-filter, enter=not-red |
| `greens-woolroom` | union | **wool_room** | block=greens-woolrooms-filter, enter=not-green |
| `yellows-woolroom` | union | **wool_room** | block=yellows-woolrooms-filter, enter=not-yellow |
| `woolrooms` | union | **wool_room** | rule_group, block_break=woolrooms-break-filter |
| `build-area` | union | **build** | — |
| `not-build-area` | negative | **other** | rule_container, block_break=block-break-void-filter, block_place=block-place-void-filter |
| `blocks-filter-region` | cylinder | **other** | — |
