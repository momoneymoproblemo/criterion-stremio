# Criterion Collection for Stremio

An unofficial catalogue add-on with genuine Criterion edition artwork, real IMDb IDs and spine-number ordering. The installation webpage has no film search or title browser. Video streams come from your existing Stremio add-ons.

## Set up on GitHub

Create a public repository named **criterion-stremio**. Extract this ZIP and upload its contents into the repository root, keeping the `docs` folder intact. Do not upload the ZIP itself. The package includes ready-to-use catalogue JSON, so no initial data download is needed to use those files.

GitHub may reject a dragged `.github` folder because it starts with a dot. Create the workflow in GitHub instead: Code → Add file → Create new file. Enter **`.github/workflows/update.yml`** as the filename, paste the contents of the ZIP's workflow file, and commit to main.

Go to Settings → Pages and select **GitHub Actions** as the source. This project deploys Pages directly from its workflow; do not select a branch folder. Then go to Actions → Update and publish Criterion → Run workflow. Wait for the green success tick.

Your webpage: `https://momoneymoproblemo.github.io/criterion-stremio/`

Your manifest: `https://momoneymoproblemo.github.io/criterion-stremio/manifest.json`

The scheduled workflow runs early each Monday in Melbourne, refreshes the collection, commits updated data and publishes it in the same run. Uploading a changed `docs/index.html` triggers publishing too. The manifest logo base URL automatically follows the actual GitHub repository name during the workflow build.

## Artwork and coverage

Catalogue cards use Criterion's hosted edition cover images rather than Metahub or TMDb posters. Film details reached through another metadata add-on may display that provider's artwork. This add-on does not replace artwork throughout Stremio. Remote cover images avoid uploading thousands of files, but depend on Criterion keeping those image URLs available.

The source includes individual films, shorts, television, box sets, anthology releases and alternate editions. Playable entries are matched to IMDb IDs and deduplicated by ID. Box-set product rows are not treated as playable films. Television entries have a separate, correctly typed catalogue. `build-report.json` records coverage, excluded compilation products and titles needing review. No fake IMDb IDs or guessed stream IDs are used.

The default view is spine order, 100 entries per page; the genre selector offers decade filters. Clear the decade filter to return to the whole collection. Films without a spine number follow the numbered collection in Criterion's source order.

## Maintaining the collection

Python 3.12+, no third-party dependencies. Run `python build.py` to refresh. Use `OFFLINE_BUILD=1 python build.py` to rebuild bundled data without fetching the Criterion list. Existing checked mappings are retained; new, unambiguous exact title/year matches use IMDb's official basics dataset. Ambiguous additions are listed in `build-report.json` for review rather than being silently matched to the wrong film. The dataset stays in `.cache`, which must never be uploaded.

For a manually checked addition, add its Criterion URL, IMDb ID, title type, runtime and genres to `matches.json`, then rebuild. Remove any corresponding exclusion if relevant. The build checks that repository files remain below 100; additional collection growth may eventually require changing the paging layout.

Names, logos and artwork belong to their respective owners. Unofficial fan project; no affiliation with Criterion, IMDb or Stremio.
