# Agent instructions

This repository currently holds planning context for the EVPN Gateway Appliance (EGA),
not product source; check the tree before assuming code exists.

- Start at `plans/context/evpn-aws/agent-guide.md`. It lists the requirements, the
  verified facts that are easy to get wrong, and which document to read for which task.
- Jira acceptance criteria are the requirements. A decision exists only when
  `plans/context/evpn-aws/kickoff-decisions.md` records its owner and date; everything
  else in those documents is a proposal.
- This repository is public. Commit no customer or support material, credentials, private
  lab inventories, raw Jira exports or internal chat. Run
  `plans/context/evpn-aws/tools/check-all.sh` before committing (add `--offline` without
  network access); it includes the public-safety scanner.
- Never push the internal prototype's git history here; import a reviewed snapshot
  (`plans/context/evpn-aws/source-audit.md#0-public-import`).
