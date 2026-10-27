# CMS Registration

CMS case setup and RRS **Complete Registration** follow Unity case creation/assignment and a supervisor's assignment to a registration agent (BRD slides 101–123). This is sequential but **decoupled**: an operator starts a separate run per claim after the handoff, not an automatic continuation of Unity or Final Code's earlier CMS customer-search stage. Investigation and evidence: [`docs/cms-registration/INVESTIGATION.md`](../../docs/cms-registration/INVESTIGATION.md), with W1–W3 reports in that directory.

- [`Deploy-Ready/`](Deploy-Ready/) owns the immutable request/candidate/step contract, the injected stage controller and lazily loaded live adapter. It is a separate parallel workstream.
- [`Stand-Alone/`](Stand-Alone/) owns the offline fixtures/runner, attended pywebview bridge, React UI, tests and source-only packaging recipe. See its [README](Stand-Alone/README.md).

Backlog: [FCM-1.1-97](../../docs/INSTRUCTIONS.md) parent module; 98 case-selection disabled in legacy; 99 unset RRS Case Id; 100 additional-provider branch reversed; 101 Claim Identifier/appointment writes; 102 Other Notes; 103 Bill To/C02283/employer policy; 104 additional CPD ERFS; 105 controlled supervisor/office references. The new module must not call the monolithic legacy registration tail as proof that these are repaired.

Owner decisions still open: source/version/deployment of supervisor mapping and office matrix; dedicated stored-procedure connection and approved secret channel; UAT vs production/live test authorization; employer-specific Bill To/C02283 and CEM rules; provider/attorney matching and ambiguity; registration-agent handoff validation and RRS row identity. Offline results do not validate portal persistence or resolve these business rules. v1.0.0 has an offline-verified EXE; no live-system verification has been performed.
