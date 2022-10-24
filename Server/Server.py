import Pyro5.api
from Pyro5.server import expose
from datetime import datetime
from threading import Lock
from Server.Appointment import Appointment


def printcall(f):
    def new(*args, **kwargs):
        print(f'{type(args[0]).__name__}.{f.__name__}', end="(")
        print(*args[1:], sep=", ", end="")
        print(**kwargs, sep=", ", end=")\n")
        f(*args, **kwargs)
    return new


class ScheduledAlerts():
    def __init__(self, event=None, appointments: list[Appointment] = []):
        self.event = event
        self.appointments = appointments


class Server(object):
    def __init__(self):
        self.users: dict[str, str] = {}
        self.usersMutex = Lock()
        self.appointments: dict[str, list[Appointment]] = {}
        self.scheduledAlerts: dict[datetime, ScheduledAlerts] = {}
        self.appointmentsMutex = Lock()
        pass

    def get_user(self, user: str):
        with self.usersMutex:
            if user not in self.users:
                return None
            return Pyro5.api.Proxy(self.users[user])

    @expose
    @printcall
    def register_user(self, user: str, uri: str):
        with self.usersMutex:
            self.users[user] = uri
        return "key"

    def add_user_appointment(self, user: str, appointment: Appointment):
        appointment.guests[user] = True
        if not self.appointments[user]:
            self.appointments[user] = []
        appointments = self.appointments[user]
        appointments.append(appointment)
        appointments.sort()

    def get_appointment_by_name(self, user: str, appointmentName: str):
        appointment = self.appointments[user] if user in self.appointments else []
        appointment = [a for a in appointment if a.name == appointmentName]
        if len(appointment) == 0:
            return None
        return appointment[0]

    def remove_user_appointment(self, user: str, appointmentName: str):
        appointment: Appointment = self.get_appointment_by_name(user, appointmentName)
        appointment.guests.pop(user, None)
        appointment.alerts.pop(user, None)
        if user in self.appointments:
            self.appointments[user] = [a for a in self.appointments[user] if a.name != appointmentName]

    def add_user_alert(self, user: str, appointment: Appointment, alert: datetime):
        appointment.alerts[user] = alert
        if alert in self.scheduledAlerts:
            self.scheduledAlerts[alert].appointments.append(appointment)
        else:
            self.scheduledAlerts[alert] = ScheduledAlerts('TODO', appointment)

    def remove_user_alert(self, user: str, appointmentName: str):
        appointment: Appointment = self.get_appointment_by_name(user, appointmentName)
        alert = appointment.alerts.pop(user, None)
        if not alert:
            return
        if len([a for a in appointment.alerts.values() if a == alert]) == 0:
            self.scheduledAlerts[alert].appointments.remove(appointment)
        if (len(self.scheduledAlerts[alert].appointments) == 0):
            # self.scheduledAlerts[alert].cancel()
            del self.scheduledAlerts[alert]

    def new_appointment_event(self, user: str, appointment: Appointment):
        user = self.get_user(user)
        user.new_appointment_event(appointment)

    def alert_event(self, user: str, appointment: Appointment):
        user = self.get_user(user)
        user.alert_event(appointment)

    @expose
    def register_appointment(self, user: str, name: str, date: datetime, guests: list[str], alerts: dict[str, datetime]):
        with self.appointmentsMutex:
            if name in self.appointments:
                print(f'Appointment {name} already registered')
            appointment = Appointment(user, name, date, guests, alerts)
            guests = appointment.guests.keys()
            while len(guests) > 0:
                guest = guests.pop()
                self.new_appointment_event(guest, appointment)
            self.add_user_appointment(user, appointment)

    @expose
    def cancel_appointment(self, user: str, appointmentName: str):
        with self.appointmentsMutex:
            self.remove_user_appointment(user, appointmentName)

    @expose
    def cancel_alert(self, user: str, appointmentName: str):
        with self.appointmentsMutex:
            self.remove_user_alert(user, appointmentName)

    @expose
    def get_appointments(self, user: str):
        with self.appointmentsMutex:
            if user in self.appointments:
                return self.appointments[user]
