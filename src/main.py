import os
import logging
import subprocess

import requests
from rich.logging import RichHandler
from rich.progress import Progress

logging.basicConfig(
    level="NOTSET", format="%(message)s",
    datefmt="[%X]", handlers=[RichHandler()]
)
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.WARNING)
log = logging.getLogger("rich")


class GhSync:
    BASE_URL = "https://api.github.com/"

    def __init__(self, backup_dir, token_path="~/.ssh/github_token", ignore=()):
        self.backup_dir = os.path.expanduser(backup_dir)
        self.token = self.read_token(token_path)
        self.ignore = ignore

        if not self.token:
            log.error("Unable to read token, quiting!")
            return

        backup_dir_exists = self.ensure_backup_dir()
        if not backup_dir_exists:
            log.error("Unable to create backup directory, quiting!")
            return

        os.chdir(self.backup_dir)

        self.repositories = self.fetch_repositories()

    def ensure_backup_dir(self):
        if os.path.exists(self.backup_dir):
            log.info("Backup directory already exists.")
            return True

        log.info(f"Creating backup directory: '{self.backup_dir}'")
        process = subprocess.run(
            ["mkdir", "-p", self.backup_dir], capture_output=True
        )
        if process.returncode != 0:
            log.error(process.stderr.decode())
            return False
        log.info(f"Backup directory created.")
        return True

    @staticmethod
    def read_token(token_path):
        path = os.path.expanduser(token_path)
        if os.path.exists(path):
            with open(path) as file:
                return file.read().strip()
        log.error("Invalid token path.")
        return False

    def fetch_repositories(self):
        endpoint = self.BASE_URL + "user/repos?per_page=100"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}"
        }
        data = []

        page = 1
        while True:
            with requests.get(endpoint + f"&page={page}", headers=headers) as response:
                json = response.json()
            data.extend(response.json())
            if len(json) < 100:
                return data
            page += 1

    def sync(self):
        with Progress() as progress:
            task = progress.add_task("Sync", total=len(self.repositories))
            for repository in self.repositories:
                full_name = repository["full_name"]
                if full_name in self.ignore:
                    continue
                subprocess.run(
                    f"git -C {full_name} pull || "
                    f"git clone git@github.com:{full_name} {full_name}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                progress.update(task, description=full_name.center(50), advance=1)


if __name__ == "__main__":
    try:
        gsync = GhSync("~/gh")
        gsync.sync()
    except KeyboardInterrupt:
        log.warning("Quiting...")
