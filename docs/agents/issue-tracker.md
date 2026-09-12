# Issue tracker: GitHub

Issues and Wayfinder maps for this repository live in GitHub Issues at `neoyipeng2018/nlp-wayfinder`. Use the `gh` CLI for tracker operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`.
- **Read an issue**: `gh issue view <number> --comments`.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments`.
- **Comment on an issue**: `gh issue comment <number> --body "..."`.
- **Apply or remove labels**: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- **Close an issue**: `gh issue close <number>` after posting its resolution.

## Wayfinding operations

- **Map**: one issue labelled `wayfinder:map`, containing Destination, Notes, Decisions so far, Not yet specified, and Out of scope.
- **Child ticket**: an issue linked to the map through GitHub's sub-issues API and labelled `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task`.
- **Child link**: fetch the child's numeric database ID with `gh api repos/neoyipeng2018/nlp-wayfinder/issues/<child-number> --jq .id`, then call `gh api --method POST repos/neoyipeng2018/nlp-wayfinder/issues/<map-number>/sub_issues -F sub_issue_id=<child-database-id>`.
- **Blocking**: use GitHub's native issue dependencies. Fetch the blocker's numeric database ID, then call `gh api --method POST repos/neoyipeng2018/nlp-wayfinder/issues/<child-number>/dependencies/blocked_by -F issue_id=<blocker-database-id>`.
- **Frontier**: preserve sub-issue order and take the first open child with no assignee and `issue_dependencies_summary.blocked_by == 0`.
- **Claim**: assign the ticket to the driving developer before doing work.
- **Resolve**: post the answer as a comment, close the ticket, then append a one-line gist and ticket link under the map's Decisions so far.

The local `.scratch/` tree is a convenience mirror only; GitHub is canonical.
