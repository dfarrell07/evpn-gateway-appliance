# Agent instructions

EVPN Gateway Appliance (EGA): the bootc image, disk images, AMI and Ansible collection that
connect OpenShift's EVPN to AWS, owned by OpenShift Core Networking. This repository is public.
People start at `plans/context/evpn-aws/README.md`; agents start below.

## Orient

- Run `ls` before assuming code exists. Planning documents live in `plans/context/evpn-aws/`;
  product source arrives through separate pull requests (for example `ansible/` and `image/`),
  so no list of directories is kept here.
- Open `plans/context/evpn-aws/agent-guide.md`. It lists the requirements, the verified facts
  that are easy to get wrong, and which document to read for which task. Open only the part a task
  needs; use its reading map instead of loading the whole directory.
- Jira acceptance criteria are the requirements. A decision exists only when
  `plans/context/evpn-aws/kickoff-decisions.md` records its owner and date; everything else in
  those documents is a proposal.
- Do not rename a plan file or renumber a decision: source comments and pull requests cite them.

## Check your change

```bash
make check OFFLINE=1   # what Prow's `verify` test runs; before committing and again before pushing
make check             # also the network checks; needs an authenticated `gh`
make check TERMS=path  # also screen for names in a private list kept OUTSIDE this repository
```

`make verify` is the same target. Offline checks need Bash, `python3`, `git` and
`yamllint` (pinned in the CI image). The existing illustration tests also use `jq` when
available; skipping them does not qualify product behavior. The plans' other tooling is
described in `plans/context/evpn-aws/ci-source.md`.

## Rules

- **Public repository.** Commit no customer or support material, credentials, private lab
  inventories, account IDs, raw Jira exports or internal chat. Cite an internal source by ticket key
  or link and summarize the finding. Never push the internal prototype's git history; import a
  reviewed snapshot (`plans/context/evpn-aws/source-audit.md#0-public-import`).
- **Commits and pull requests.** Start the title with a Jira key (`CORENET-1234: ...`), which tide
  requires, and sign off every commit (`git commit -s`). One logical change per commit.
- **Adding CI.** Follow `plans/context/evpn-aws/ci-source.md`: one check per pull request, its logic
  in a Make target, the tool pinned in `Dockerfile.root` in an earlier pull request (Prow builds it
  from the base branch), and a seeded failing input shown to fail.
  Prefer a maintained tool to a script; custom code needs an entry in that file's budget.
- **Facts.** Cite a repository, revision and path for an implementation claim, and say whether it
  is merged code, deployed capability or qualified behavior.
