window.BENCHMARK_DATA = {
  "lastUpdate": 1794313890387,
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
          "id": "ef7ecc82bbf0b61bdc7de13e6b8bcd959859b996",
          "message": "authorize runs in the workflow itself",
          "timestamp": "2026-11-06T14:30:44Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/ef7ecc82bbf0b61bdc7de13e6b8bcd959859b996"
        },
        "date": 1793975580412,
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
          "id": "34915999cf86ff50ce7fa449ea0d037723a4494c",
          "message": "set the expected commit in the workflow\n\n- Inject EXPECTED_COMMIT_SHA for the selected commit and reject malformed or duplicate pipeline variables\n- Name both commits when GitLab runs another commit than selected\n- Drop EXPECTED_COMMIT_SHA from the callers and examples\n- Remove the test account exception from the PR command\n- Ask to review earlier commits on their own before naming them\n- Pin github2lab_action to 74a6aac",
          "timestamp": "2026-11-06T15:26:07Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/34915999cf86ff50ce7fa449ea0d037723a4494c"
        },
        "date": 1793979289053,
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
          "id": "4def4507b34918a44355041328d3310e5a610240",
          "message": "make the PR command a reusable workflow",
          "timestamp": "2026-11-06T16:18:51Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/4def4507b34918a44355041328d3310e5a610240"
        },
        "date": 1793982079623,
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
          "id": "6fd64e50ceca2e0264d28af0ae4b28606266d44f",
          "message": "list only recent runs while waiting for a continuation",
          "timestamp": "2026-11-06T17:00:15Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/6fd64e50ceca2e0264d28af0ae4b28606266d44f"
        },
        "date": 1793985867380,
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
          "id": "8dfba7a2d374dcb57c7e94901d10d8828c10d332",
          "message": "more clear text",
          "timestamp": "2026-11-06T23:01:51Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/8dfba7a2d374dcb57c7e94901d10d8828c10d332"
        },
        "date": 1794006237307,
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
          "id": "58f6bf270de20d78d395877306e627c25f0c53d5",
          "message": "update github2lab_action",
          "timestamp": "2026-11-06T23:23:09Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/58f6bf270de20d78d395877306e627c25f0c53d5"
        },
        "date": 1794007519670,
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
          "id": "499b0d0c0729a16761d9cdda86263e820af97cf5",
          "message": "update coverage by example caller",
          "timestamp": "2026-11-07T16:58:07Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/499b0d0c0729a16761d9cdda86263e820af97cf5"
        },
        "date": 1794070826430,
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
          "id": "499b0d0c0729a16761d9cdda86263e820af97cf5",
          "message": "update coverage by example caller",
          "timestamp": "2026-11-07T16:58:07Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/499b0d0c0729a16761d9cdda86263e820af97cf5"
        },
        "date": 1794197029305,
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
          "id": "1eaa31d7e9035ea9c662af1bfd18d90a6654804d",
          "message": "record complete benchmark series of failed pipelines",
          "timestamp": "2026-11-09T07:43:02Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/1eaa31d7e9035ea9c662af1bfd18d90a6654804d"
        },
        "date": 1794211298799,
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
          "id": "96c7e8866b9be6977f60fc6dfc29b9833f364d7b",
          "message": "add reactions to PR comment",
          "timestamp": "2026-11-10T12:29:15Z",
          "url": "https://github.com/pc2/hpc-cb-workflow/commit/96c7e8866b9be6977f60fc6dfc29b9833f364d7b"
        },
        "date": 1794313890376,
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