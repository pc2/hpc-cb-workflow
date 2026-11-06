window.BENCHMARK_DATA = {
  "lastUpdate": 1793974080875,
  "repoUrl": "https://github.com/pc2/hpc-cb-workflow",
  "entries": {
    "Regression fixture": [
      {
        "commit": {
          "author": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "committer": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "id": "45b8d1355fd00e09a6a516ea41a6c1bc1c8f5c23",
          "message": "integrate github-action-benchmark",
          "timestamp": "2026-11-04T21:57:13Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/45b8d1355fd00e09a6a516ea41a6c1bc1c8f5c23"
        },
        "date": 1793829835717,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "controlled measurement",
            "value": 100,
            "unit": "seconds"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "committer": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "id": "2befa6af9c5d680ae34255614b3c367c107d69c3",
          "message": "extend CI coverage",
          "timestamp": "2026-11-04T22:16:05Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/2befa6af9c5d680ae34255614b3c367c107d69c3"
        },
        "date": 1793830688729,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "controlled measurement",
            "value": 100,
            "unit": "seconds"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "committer": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "id": "3405033391b7199882e2dbddf8825917b24696cf",
          "message": "allow failure where expected",
          "timestamp": "2026-11-04T22:37:33Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/3405033391b7199882e2dbddf8825917b24696cf"
        },
        "date": 1793831980785,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "controlled measurement",
            "value": 100,
            "unit": "seconds"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "committer": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "id": "73febcf2a9c616984ad699c3e9b675a74077fb96",
          "message": "update README",
          "timestamp": "2026-11-05T08:35:05Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/73febcf2a9c616984ad699c3e9b675a74077fb96"
        },
        "date": 1793867842598,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "controlled measurement",
            "value": 100,
            "unit": "seconds"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "committer": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "id": "688c010311d48c780ea808d7a103400c6724df74",
          "message": "update github2lab_action",
          "timestamp": "2026-11-05T09:46:56Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/688c010311d48c780ea808d7a103400c6724df74"
        },
        "date": 1793872148903,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "controlled measurement",
            "value": 100,
            "unit": "seconds"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "committer": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "id": "602c666dcc442b475bb4af676249670847af7f44",
          "message": "update github2lab_action",
          "timestamp": "2026-11-05T09:46:56Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/602c666dcc442b475bb4af676249670847af7f44"
        },
        "date": 1793895576472,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "controlled measurement",
            "value": 100,
            "unit": "seconds"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "committer": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "id": "7cffcd8416936c6b1de04c549d577888aad4cdd5",
          "message": "harden monitoring, PR command and collection\n\n- Retry continuation dispatches and tolerate GitLab outages during monitoring\n- Cover all jobs and child pipelines in checks and collected artifacts\n- Require /hpc <commit> and dispatch only when the PR head matches the reviewed commit\n- Start pipelines on pushes to the default branch instead of a hardcoded main\n- Let pipelines without artifacts pass collection and report the archive count\n- End monitoring with status manual when a manual job blocks the pipeline\n- Pin github2lab_action to 721e2ab",
          "timestamp": "2026-11-06T13:46:08Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/7cffcd8416936c6b1de04c549d577888aad4cdd5"
        },
        "date": 1793972939780,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "controlled measurement",
            "value": 100,
            "unit": "seconds"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "committer": {
            "name": "Gerrit Pape",
            "username": "papeg",
            "email": "gerrit.pape@uni-paderborn.de"
          },
          "id": "a25be9a34d9d528b25a896188f864ed09cfd0380",
          "message": "pass variables for possible job selection",
          "timestamp": "2026-11-06T14:05:41Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/a25be9a34d9d528b25a896188f864ed09cfd0380"
        },
        "date": 1793974080865,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "controlled measurement",
            "value": 100,
            "unit": "seconds"
          }
        ]
      }
    ]
  }
}