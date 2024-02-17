import argparse
import sys

import requests
from bs4 import BeautifulSoup
import datetime
import threading

import configparser

config = configparser.ConfigParser()
config.read('config.cfg')


def execute_menu(parser):
    arg = parser.parse_args()
    _nauta = PortalNauta()
    if True:
        threading.Thread(target=_nauta.do_login()).start()
    elif arg.o:
        threading.Thread(target=_nauta.do_logout()).start()
    else:
        parser.print_help()


class PortalNauta:
    def __init__(self):
        self.user_passw_error = -1
        self.estado_cuenta = None
        self.saldo_cuenta = None
        source_hostname: str = 'secure.etecsa.net'
        source_port: str = '8443'
        self.source_url: str = "https://" + source_hostname + ":" + source_port
        self.source_url_query_servlet: str = self.source_url + "/EtecsaQueryServlet"
        self.source_url_login_servlet: str = self.source_url + "//LoginServlet"
        self.source_url_logout_servlet: str = self.source_url + "/LogoutServlet"
        self.csrfhw: str = ""
        self.cookies = ""
        self.header = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/102.0",
                       "Accept-Encoding": "gzip, deflate, br", }

    def username(self):
        return config.get('CREDENTIAL', "username")

    def password(self):
        return config.get('CREDENTIAL', "password")

    def logger_id(self):
        return config.get('INFO', "logger_id")

    def attr_uuid(self):
        return config.get('INFO', "attr_uuid")

    def set_attr_uuid(self, _attr_uuid):
        config.set('INFO', 'attr_uuid', _attr_uuid)
        # config.set('INFO', 'wlanuserip', )
        # writing the necessary info to the file to use later in the logout
        with open('config.cfg', 'w') as configfile:
            config.write(configfile)

    def set_logger_id(self, _logger_id):
        config.set('INFO', 'logger_id', _logger_id)
        # writing the necessary info to the file to use later in the logout
        with open('config.cfg', 'w') as configfile:
            config.write(configfile)

    def _data(self):
        return {
            "wlanacname": "",
            "wlanmac": "",
            "firsturl": "notFound.jsp",
            "ssid": "",
            "usertype": "",
            "gotopage": "/nauta_etecsa/LoginURL/mobile_login.jsp",
            "successpage": "/nauta_etecsa/OnlineURL/mobile_index.jsp",
            "loggerId": self.logger_id,
            "lang": "es_ES",
            "username": self.username(),
            "password": self.password(),
            "CSRFHW": self.csrfhw
        }

    def begin(self):
        # save logger_id in config.cfg
        self.set_logger_id(datetime.datetime.now().strftime("%Y%m%d%H%M%S%f"))
        execute = requests.get(self.source_url, timeout=10)
        soup = BeautifulSoup(execute.content, "html.parser")
        # get CSRFHW
        self.csrfhw = soup.select_one("input[name=CSRFHW]")["value"]
        # get cookies
        self.cookies = execute.cookies

    def state(self):
        try:
            self.begin()
            post = requests.post(self.source_url_query_servlet, data=self._data(),
                                 cookies=self.cookies, allow_redirects=True, headers=self.header)
            _soup = BeautifulSoup(post.content, "html.parser")

            if "alert(\"return null\");" not in str(_soup.select("script")[-1]):
                self.estado_cuenta = _soup.select("table#sessioninfo > tbody > tr > td")[3].text
                self.saldo_cuenta = _soup.select("table#sessioninfo > tbody > tr > td")[1].text
                print("estado: ", self.estado_cuenta)
                print("saldo: ", self.saldo_cuenta)
        except Exception as e:
            print(e)
            pass

    def do_login(self):
        try:
            self.begin()
            _loggin = requests.post(self.source_url_login_servlet,
                                    data={"username": self.username(), "password": self.password()},
                                    allow_redirects=True, timeout=10, headers=self.header)

            _soup = BeautifulSoup(_loggin.content, "html.parser")

            if "El nombre de usuario o contraseña son incorrectos" in _loggin.text:
                # Password is incorrect.
                self.user_passw_error = 1
            elif "No se pudo autorizar al usuario" in _loggin.text:
                # The user is incorrect.
                self.user_passw_error = 2
            elif "Usted a realizado muchos intentos" in _loggin.text:
                # Many attempts
                self.user_passw_error = 3
            elif "Su tarjeta no tiene saldo disponible" in _loggin.text:
                # No account balance
                self.user_passw_error = 4

            print(_soup.select_one("script").text.split("ATTRIBUTE_UUID=")[1].split("&")[0])
            # save attr_uuid in config.cfg
            self.set_attr_uuid(_soup.select_one("script").text.split("ATTRIBUTE_UUID=")[1].split("&")[0])
            print("Satisfactorily authenticated")
        except Exception as e:
            print(e)
            raise e

    def do_logout(self):
        data_logout = {'username': self.username(), 'ATTRIBUTE_UUID': self.attr_uuid(), 'wlanacname': '', 'domain': '',
                       'remove': 1, "loggerId": f"{self.logger_id()}+{self.username()}"}
        try:
            post_request = requests.post(self.source_url_logout_servlet, data=data_logout, timeout=10,
                                         headers=self.header)
        except requests.exceptions.RequestException as e:
            print(e)
            raise e
        else:
            print("Logout satisfactorily")


def validate_config():
    """validate the existence of the configuration file and some options"""
    _sections = ['CREDENTIAL', 'INFO']
    _cred_options = ['username', 'password']
    _info_options = ['attr_uuid', 'logger_id', 'wlanuserip']

    result_1 = all(x == y for x, y in zip(_cred_options, config.options('CREDENTIAL')))
    result_2 = all(x == y for x, y in zip(_info_options, config.options('INFO')))

    _username = config.get('CREDENTIAL', 'username')
    _password = config.get('CREDENTIAL', 'password')

    if result_1 and result_2 and len(_username) and len(_password):
        return True
    return False


def start():
    if not validate_config():
        print("Check the configuration file")
        sys.exit(1)
    parser = argparse.ArgumentParser(description='Portal Nauta Options')
    parser.add_argument('-l', '-login', action='store_true', help='To sign-in')
    parser.add_argument('-o', '-logout', action='store_true', help='To sign-out')
    execute_menu(parser)


if __name__ == '__main__':
    start()
