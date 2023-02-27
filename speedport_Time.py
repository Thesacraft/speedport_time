import json
import logging
import os.path
import subprocess
import threading
import time
import webbrowser

import selenium.common.exceptions
from infi.systray import SysTrayIcon
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options


class RequestHandler:
    def __init__(self, logger: logging.Logger, debug: bool = False,
                 url: str = "http://speedport.ip/html/login/clienttime.html?lang=de#"):
        self._options = Options()
        if not debug:
            self._options.add_argument("-headless")  # makes it invisible
        self._driver: webdriver.Firefox = None
        self._url = url
        self._logger = logger
        self._create_browser()

    def _create_browser(self):
        self._logger.info("Starting Firefox...")
        self._driver = webdriver.Firefox(options=self._options)
        self._driver.get(self._url)

    def _make_sure_running(self):
        try:
            temp = self._driver.current_url
            del temp
        except selenium.common.exceptions.WebDriverException:
            self._create_browser()

    def get_values(self) -> dict:
        self._make_sure_running()
        if self._driver.current_url == self._url:
            self._driver.refresh()
        self._driver.get(self._url)
        time.sleep(0.3)
        div_timelimit_yes = self._driver.find_element(By.ID, "timeruleTimeYes")
        remaining_time = self._driver.find_element(By.ID, "var_remainingtime").text
        now = self._driver.find_element(By.ID, "var_time").text
        try:
            divs_from_to = []
            for i in range(1, 4):
                temp = [self._driver.find_element(By.ID, f"time_line{i}").is_displayed(),
                        self._driver.find_element(By.ID, f"var_trule_from{i}").text,
                        self._driver.find_element(By.ID, f"var_trule_to{i}").text]
                divs_from_to.append(temp)
        except selenium.common.exceptions.NoSuchElementException:
            return {}
        values = {"Timelimit": div_timelimit_yes.is_displayed(), "timestamp": now, "remaining_time": remaining_time,
                  "from_to_1": divs_from_to[0], "from_to_2": divs_from_to[1], "from_to_3": divs_from_to[2]}

        return values

    def quit(self):
        self._driver.quit()


def _clean_message(message: list) -> str:
    length = len(max(message, key=len)) + 4
    if length < 30:
        length = 30
    final_message = f'\n\n{"#" * (length + 2)}\n'
    for line in message:
        final_message += f"#{line:^{length}}#\n"
    final_message += f'{"#" * (length + 2)}\n'
    return final_message


def _author():
    webbrowser.open("https://www.github.com/Thesacraft")


class TimeMain:
    def __init__(self, config_path: str = "config.json", debug: bool = False, path_icon: str = "icon.ico"):

        self._config_path = config_path
        self._log_level = "INFO"
        self._load_config()
        self._log_file = "logfile-speedport-time.log"
        self._debug = debug
        self._offset = 60
        self._setup_logging()
        self._request_handler = RequestHandler(self._logger, debug=self._debug)
        self._systray: SysTrayIcon = None
        self._icon_icon = path_icon
        self._running = False
        self._menu_options = (
            ("Update timing", None,
             (("Update every minute", None, lambda x: self._update_config("update_offset", 60)),
              ("Update every 2 minutes", None, lambda x: self._update_config("update_offset", 120)),
              ("Update every 4 minutes", None, lambda x: self._update_config("update_offset", 240)),
              )
             ), (
                ("Logging", None, (
                    ("Debug", None, lambda x: self._update_config("Loglevel", "DEBUG")),
                    ("Info", None, lambda x: self._update_config("Loglevel", "INFO")),
                    ("Warning", None, lambda x: self._update_config("Loglevel", "WARNING")),
                    ("Open Logs", None, lambda x: subprocess.Popen(f"notepad.exe {self._log_file}")),
                )
                 )
            ),
            (
                "Restart", None, lambda x: self._restart()
            ),
            ("ClearLog", None, lambda x: self._clear_log()),
            ("Author", None, lambda x: _author()),
        )
        self._start()

    def _load_config(self):
        standard_config = """{
"Loglevel": "DEBUG",
"icon_path": "icon.ico",
"update_offset": 60,
"hide_cmd":"hide.vbs"
}"""
        standard_vbs = """
set Shell = WScript.CreateObject("WScript.Shell")
Shell.Run("speedport_Time.py"),0
"""

        if not os.path.exists(self._config_path):
            with open(self._config_path, "w+") as file:
                file.write(standard_config)

        with open(self._config_path, "r") as json_file:
            config = json.load(json_file)
        self._log_level = config["Loglevel"]
        self._offset = config["update_offset"]
        self._icon_icon = config["icon_path"]
        self._hide_cmd = config["hide_cmd"]
        if not os.path.exists(self._hide_cmd):
            with open(self._hide_cmd, "w+") as file:
                file.write(standard_vbs)

    def _update_config(self, option: str, value):
        with open(self._config_path, "r") as json_file:
            config = json.load(json_file)
        if option not in config.keys():
            return
        config[option] = value
        self._logger.warning(f"Updating {option} to {value}!")

        with open(self._config_path, "w") as json_file:
            json_file.write(json.dumps(config))
        if option == "Loglevel":
            self._restart("Automatically restarting because of a change of the LogLevel")



    def _restart(self,reason:str=None):
        command = f'taskkill /F /PID {os.getpid()} && start {self._hide_cmd}'
        self._on_quit()
        if reason is not None and self._log_level == "DEBUG":
            self._logger.info(_clean_message(["Restarting...",f"Reason:{reason}"]))
        else:
            self._logger.info(_clean_message(["Restarting..."]))
        subprocess.Popen(command, shell=True)

    def _clear_log(self):
        with open(self._log_file, "r") as file:
            text = file.read()
        text = text[::-1]
        start = "]trats["
        text_splitted = text.split(start)
        with open(self._log_file, "w") as file:
            file.write(text_splitted[0][::-1])
        self._logger.warning("Cleared the logs!")

    def _setup_logging(self):
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(lineno)d - %(message)s')
        handler = logging.FileHandler(self._log_file, encoding="utf-8")
        handler.setFormatter(formatter)
        logging.basicConfig(handlers=[handler],level=self._log_level)
        self._logger = logging.getLogger("speedport_Time")
        self._logger.setLevel(self._log_level)
        self._logger.warning("[start]")
        self._logger.info(_clean_message(["Starting...",f"Loging-Level: {self._log_level}",f"Updatetiming: {self._offset}"]))

    def _start(self):
        size_in_mb = round(os.stat(self._log_file).st_size / (1024 * 1024), 2)
        if size_in_mb > 2:
            self._logger.warning(
                f"Automatically clearing the logs, because the file was getting to big({size_in_mb}MB)!")
            self._clear_log()
        self._systray = SysTrayIcon(self._icon_icon, "Starting...", self._menu_options,
                                    on_quit=lambda x: self._on_quit(), default_menu_index=7)
        self._systray.start()
        self._logger.info("Starting Systray")

    def _update_time(self):
        hov_text = f""
        values = self._request_handler.get_values()
        connection_possible = "Nein"
        if values["Timelimit"]:
            connection_possible = "Ja"
        remaining_time = values['remaining_time']
        if remaining_time == '':
            remaining_time = 'Unbeschränkt'
        hov_text += f"Verbleibende Zeit: {remaining_time}\n"
        for item in (values["from_to_1"], values["from_to_2"], values["from_to_3"]):
            if item[0]:
                hov_text += f"Du kannst dich zwischen {item[1]} - {item[2]} Verbinden\n"
        hov_text += f"Verbindung Heute Möglich: {connection_possible}\n"
        hov_text += f"Letztes Update: {values['timestamp']}"
        self._systray.update(self._icon_icon, hov_text)
        self._logger.debug("Updated the hover text")

    def _mainloop(self):
        self._running = True
        while self._running:
            self._update_time()
            self._load_config()
            time.sleep(self._offset)

    def _on_quit(self):
        self._running = False
        self._logger.info(_clean_message(["Exiting..."]))
        self._request_handler.quit()

    def run(self):
        thread_mainloop = threading.Thread(target=self._mainloop, daemon=True)
        thread_mainloop.start()
        self._logger.info("Starting Mainloop")


if __name__ == "__main__":
    main = TimeMain(debug=False)
    main.run()
