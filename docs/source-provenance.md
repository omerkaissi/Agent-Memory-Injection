# Source provenance for the published studies

The study records retain the original local commit identifiers and file hashes. Public publication used the connected GitHub API after local Git authentication failed. GitHub assigned new commit IDs because publication metadata changed; every uploaded source tree was checked against the original Git tree hash. The original study records and local commits were not rewritten.

A Git tree hash commits to file paths, modes and blob contents. Matching trees establish the same source snapshot, not identical commit metadata or independent authentication of model outputs. The original public repository history remains the ancestor of this release. The original frozen study records are now public; see [evidence downloads and offline reanalysis](../data/README.md).

| Local snapshot | Public counterpart | Identical Git tree |
|---|---|---|
| `96e81556069c3641d9abe4eed201447cb6c73884` | [0e0eb3f](https://github.com/omerkaissi/Agent-Memory-Injection/commit/0e0eb3ff00a12d1180f8ea8c73edece9262fc1ca) | `a3279bf0f91e14fc26b8fd09657b5602db6317ea` |
| `8452ab3a01c733ebae4d0218bf7b61e0deee0375` | [2b9eedb](https://github.com/omerkaissi/Agent-Memory-Injection/commit/2b9eedb5eb496ffffcc44615244617b253bacb02) | `a6a86491ca9e23572889a90350633bcdbcfff067` |
| `dbdc859ab4077e2d3802165b795c21db4e3b6906` | [96fdd8b](https://github.com/omerkaissi/Agent-Memory-Injection/commit/96fdd8bdb0ab573e52b3a9a6abfd967a59a49065) | `99e14525fd0c604ab1087fb39c559ef1b7a21027` |
| `9cdb719199e66e94bde2531dccae65959962af55` | [77105c5](https://github.com/omerkaissi/Agent-Memory-Injection/commit/77105c5616373f27d79a63f2d0aefa07f282e4de) | `36741e230bfd4f4f624571163543d73644e64229` |
| `746d0e4d181934c550014fb802855fbd71764eff` | [8fa00bb](https://github.com/omerkaissi/Agent-Memory-Injection/commit/8fa00bb6ddb351dc55b7b022d7b4a47f98bba788) | `e3497a32a52f4c3d3284acc985bfa2403f19a089` |
| `011b0ed8377a85aaed55bb98b3d6702c65c0a46f` | [9ede0e8](https://github.com/omerkaissi/Agent-Memory-Injection/commit/9ede0e88f5c4f2be8db12581dbb5a2cc6157e61a) | `c8958b97bbd5a984159b5acd8ea03a1fc5b2c571` |

The first study's executed source bytes were retained in local snapshot `96e81556069c3641d9abe4eed201447cb6c73884` after its run; its original dirty-source metadata remains intact. The second executed local commit was `9cdb719199e66e94bde2531dccae65959962af55`. Use their public counterparts above to inspect those source snapshots. Later commits add audit tools and reports; no post-collection scorer changes are implied by this mapping.
