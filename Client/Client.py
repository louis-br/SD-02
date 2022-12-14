import Pyro5.api
import Pyro5.errors
from Pyro5.server import expose
from concurrent.futures import ThreadPoolExecutor
from Utils.Appointment import Appointment
from Utils.EventHistory import EventHistory
from Utils.Cryptography.Signer import Signer
from cryptography.exceptions import UnsupportedAlgorithm
from Client.AppointmentEventMenu import AppointmentEventMenu
from Client.AlertEventMenu import AlertEventMenu
from datetime import datetime
import sys


sys.excepthook = Pyro5.errors.excepthook


class Client():
    def __init__(self, context: EventHistory, nameserver: str, port: int, service: str):
        self.context: EventHistory = context
        self.user: str = ""

        self.service: str = service
        self.nameserver = Pyro5.api.locate_ns(nameserver, port)
        self.serverURI: str = self.nameserver.lookup(service)
        self.server = Pyro5.api.Proxy(self.serverURI)

        self.daemon = Pyro5.server.Daemon()
        self.URI: str = self.daemon.register(self)
        self.thread: ThreadPoolExecutor = ThreadPoolExecutor()
        self.thread.submit(self.request_loop)

        self.public_key = None
        self.signer = Signer()

    def request_loop(self):
        self.daemon.requestLoop()

    def shutdown(self):
        self.server._pyroRelease()
        self.daemon.shutdown()
        self.thread.shutdown(True)

    def __del__(self):
        self.shutdown()

    def register_user(self, user: str):
        self.user = user
        self.public_key = self.server.register_user(user, self.URI)
        print(self.public_key)
        self.signer.from_public_key_b64(self.public_key)

    def register_appointment(self, name: str, date: datetime, guests: dict[str, True], alerts: dict[str, datetime]):
        date = date.timestamp()
        alerts = {user: alert.timestamp() for user, alert in alerts.items()}
        self.server.register_appointment(self.user, name, date, guests, alerts)

    def cancel_appointment(self, appointmentName: str):
        self.server.cancel_appointment(self.user, appointmentName)

    def register_alert(self, owner: str, appointmentName: str, alert: datetime):
        alert = alert.timestamp()
        self.server.register_alert(self.user, owner, appointmentName, alert)

    def cancel_alert(self, appointmentName: str):
        self.server.cancel_alert(self.user, appointmentName)

    def get_appointments(self):
        return self.server.get_appointments(self.user)

    @expose
    def new_appointment_event(self, appointment: dict[str], signature: str):
        try:
            self.signer.verify_b64(signature, self.signer.json_dict_bytes(appointment))
            lastState = self.context.state
            self.context.change_state(AppointmentEventMenu(self, lastState, appointment))
        except UnsupportedAlgorithm:
            input("Invalid signature! ")

    @expose
    def alert_event(self, appointment: dict[str]):
        lastState = self.context.state
        self.context.change_state(AlertEventMenu(lastState, appointment))
