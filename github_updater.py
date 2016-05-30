#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime
import logging as log
import argparse
import os

import pytz
from github import Github
import rethinkdb as r

GITHUB_UPDATE_S = 5*60
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_ORGANISATION = os.getenv("GITHUB_ORGANISATION", "ConnectedVentures")

RETHINK_HOST = "localhost"
RETHINK_PORT = 28015
RETHINK_DATABASE = "test"


@asyncio.coroutine
def updater(con):
    last_scan = None
    def has_updated(repo):
        return repo.updated_at > last_scan

    org = get_org()
    while True:
        gh_repos = org.get_repos()

        # If not scanning for the first time only keep repositories which
        # have been updated on Github since the last repository cache update
        if last_scan is not None:
            gh_repos = [repo for repo in gh_repos if has_updated(repo)]
        last_scan = datetime.now()

        # Names of Github repositories to update or insert in database
        repo_names = [repo.name for repo in gh_repos]

        # Names of Github repositories that are in the previous list
        # AND in our table already
        db_repo_names = [repo["name"] for repo in r.table("repositories").filter(
            r.row["name"] in repo_names).pluck("name").run(con)]

        # Go over all tables that have been updated since last scan
        for gh_repo in gh_repos:
            # Add timezone to Github dates
            pushed_at = gh_repo.pushed_at.replace(tzinfo=pytz.UTC)
            updated_at = gh_repo.updated_at.replace(tzinfo=pytz.UTC)

            this_repo = {
                "name": gh_repo.name,
                "description": gh_repo.description,
                "html_url": gh_repo.html_url,
                "pushed_at": pushed_at,
                "updated_at": updated_at,
                "versions": {
                    "production": "1.2.3",
                    "staging": "1.3",
                    "testing": "0.0.0-feature-hello",
                }
            }

            if gh_repo.name in db_repo_names:
                # This repository already exists in the table but needs to be
                # updated
                log.debug("Update repo %s", gh_repo.name)
                r.table("repositories").filter(r.row["name"] == gh_repo.name).update(this_repo).run(con)
            else:
                # Insert as it"s not in the table
                log.debug("Insert repo %s", gh_repo.name)
                r.table("repositories").insert(this_repo).run(con)

        yield from asyncio.sleep(GITHUB_UPDATE_S)


def get_org():
    gh = Github(client_id=GITHUB_CLIENT_ID, client_secret=GITHUB_CLIENT_SECRET)
    return gh.get_organization(GITHUB_ORGANISATION)

def main():
    # Set up logging
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d", "--debug",
        help="Print lots of debugging statements",
        action="store_const", dest="loglevel", const=log.DEBUG,
        default=log.WARNING,
    )
    parser.add_argument(
        "-v", "--verbose",
        help="Be verbose",
        action="store_const", dest="loglevel", const=log.INFO,
    )
    args = parser.parse_args()
    log.basicConfig(level=args.loglevel)

    con = r.connect("localhost", 28015)
    db = r.db(RETHINK_DATABASE)
    if "repositories" not in db.table_list().run(con):
        db.table_create("repositories").run(con)
    else:
        print("table already exists")

    loop = asyncio.get_event_loop()
    try:
        asyncio.async(updater(con))
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print("close")
        loop.close()

if __name__ == "__main__":
    main()
