import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BambuLabOTA:
    def __init__(self):
        self.account = os.getenv("BAMBU_ACCOUNT")
        self.password = os.getenv("BAMBU_PASSWORD")
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.repo_name = "lunDreame/user-bambulab-firmware"
        self.author_name = "lunDreame"
        self.author_email = "lundreame34@gmail.com"
        self.login_url = "https://bambulab.com/api/sign-in/form"
        self.api_url = "https://api.bambulab.com"
        self.device_id = None
        self.access_token = None
        self.github = Github(self.github_token)

        if not self.account or not self.password or not self.github_token:
            self.prompt_user_account()
        else:
            self.login()

    def prompt_user_account(self):
        self.account = input("Please enter your Bambu Lab cloud account: ")
        self.password = input("Please enter the password for the Bambu Lab Cloud: ")
        self.github_token = input("Please enter your GitHub token: ")
        self.login()

    def login(self):
        try:
            response = requests.post(self.login_url, data={"account": self.account, "password": self.password})
            response.raise_for_status()
            self.access_token = response.cookies.get("token")
            if response.status_code == 200 and not response.json().get("tfaKey"):
                logging.info("BambuLab Cloud Login Successful")
                self.get_user_devices()
            else:
                logging.error("BambuLab Cloud Login Failed")
        except requests.RequestException as e:
            logging.error(f"An error occurred during login: {e}")

    def get_user_devices(self):
        try:
            response = requests.get(f"{self.api_url}/v1/iot-service/api/user/bind", headers={"authorization": f"Bearer {self.access_token}"})
            response.raise_for_status()
            devices = response.json().get("data", [])
            if devices:
                self.device_id = devices[0].get("device_id")
                logging.info(f"Device ID: {self.device_id}")
                self.get_device_firmware()
            else:
                logging.warning("No devices found.")
        except requests.RequestException as e:
            logging.error(f"An error occurred while fetching user devices: {e}")

    def get_device_firmware(self):
        if not self.device_id:
            logging.warning("Device ID is not set.")
            return
        try:
            response = requests.get(f"{self.api_url}/v1/iot-service/api/device/firmware?device_id={self.device_id}", headers={"authorization": f"Bearer {self.access_token}"})
            response.raise_for_status()
            firmware_data = response.json().get("data", {})
            printer_name, firmware_optional = self.process_firmware_data(firmware_data)
            self.compare_and_create_pull_request(printer_name, firmware_optional)
        except requests.RequestException as e:
            logging.error(f"An error occurred while fetching device firmware: {e}")

    def process_firmware_data(self, firmware_data):
        printer_name = firmware_data.get("name", "unknown_printer")
        firmware_optional = {
            "firmware_optional": {
                "stable": {
                    "device": [
                        {
                            "name": printer_name,
                            "version": firmware_data.get("version", "unknown_version"),
                            "status": "stable"
                        }
                    ],
                    "firmware_current": firmware_data.get("current_firmware")
                }
            }
        }
        return printer_name, firmware_optional

    def compare_and_create_pull_request(self, printer_name: str, firmware_optional: Dict):
        new_content = json.dumps(firmware_optional, indent=4)
        file_path = f"assets/{printer_name}_AMS.json"
        repo = self.github.get_repo(self.repo_name)

        try:
            contents = repo.get_contents(file_path, ref="main")
            old_content = contents.decoded_content.decode("utf-8")

            if new_content == old_content:
                logging.info("No changes detected in the firmware optional JSON.")
                return
            else:
                logging.info("Changes detected, creating a pull request.")
        except GithubException:
            logging.info("File does not exist, creating a new one.")

        branch_name = "schedule-update"
        try:
            main_ref = repo.get_git_ref("heads/main")
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_ref.object.sha)
        except GithubException as e:
            logging.error(f"Error creating branch: {e}")

        try:
            repo.create_file(
                file_path,
                f"Update {printer_name}_AMS JSON file",
                new_content,
                branch=branch_name,
                author=InputGitAuthor(self.author_name, self.author_email)
            )

            repo.create_pull(
                title=f"Update {printer_name}_AMS JSON file",
                body=f"The {printer_name}_AMS JSON file has been updated.",
                head=branch_name,
                base="main"
            )
            logging.info("Pull request created successfully.")
        except GithubException as e:
            logging.error(f"Error creating pull request: {e}")

if __name__ == '__main__':
    BambuLabOTA()
