# One-time per-machine setup for the jobs.json JSON-aware merge driver.
#
# Merge drivers are local git config, NOT something a repo can ship/distribute
# via .gitattributes alone (that's by design -- .gitattributes only says WHICH
# driver name to use for a path; the driver's actual command has to be
# registered locally per clone, since it's arbitrary code execution).
# Run this once on every machine that clones this repo (scraper PC, tailoring
# PC, any new machine) so jobs.json merges/rebases go through
# git_jobs_merge_driver.py instead of git's default line-based merge.
#
# Must be run from the repo root.

git config merge.jobsjson.name "JSON-aware per-job-id merge for jobs.json"

# Deliberately a RELATIVE path with no embedded quotes: git invokes merge
# drivers with cwd = the repo root, and an absolute path wrapped in "..."
# here breaks on Windows PowerShell (embedded double-quotes inside a
# single git-config value get mis-split by native argv parsing, silently
# corrupting the config -- see CLAUDE.md).
git config merge.jobsjson.driver "python git_jobs_merge_driver.py %O %A %B"

Write-Output "Registered. Verify with:"
Write-Output "  git config --get merge.jobsjson.driver"
Write-Output "  git config --get merge.jobsjson.name"
