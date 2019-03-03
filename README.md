# TOR

This project contains python scripts that enable the analysis of reliability metrics and causes of failures in the tor network.

cp1.py:

This script builds two of virtual circuits of the following form.
- Fixed fast guard * several other relays
- Several other relays * fixed fast exit

The other relays are fetched from the remote directory authorities that contain relay information belonging to the tor network.

GET requests to a webpage are made over this established circuit and the causes of failures are noted, if any. Latencies specific to fetching the webpage are noted as well.

Execute: RUN tor in the background; Parallely run python cp1.py
Note: Requires library installations (example: pycurl)

Sample errors (from previous runs):
- failures.log
- Stdout data: out
- tor terminal output: Terminal Saved Output
