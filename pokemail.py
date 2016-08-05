import tornado.ioloop
import tornado.web
import tornado.autoreload

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage

import re
import smtplib

from datetime import datetime
from pytz import timezone

import time
import json

tornado.autoreload.watch('./config.json')
with open('./config.json') as f:
    config = json.load(f)

tornado.autoreload.watch('./pokeman.json')
with open('./pokemon.json') as f:
    POKEDEX = json.load(f)['pokemon']

tornado.autoreload.watch('./wanted.json')
with open('./wanted.json') as f:
    WANTED = set(json.load(f))

encounters = set()
utc = timezone('UTC')
mytz = timezone(config.get('timezone', 'US/Eastern'))

"""
example webhook payload

{
    "type": "pokemon",
    "message": {
        "encounter_id": 1234,
        "spawnpoint_id": 4321,
        "pokemon_id": 3,
        "latitude": 39.639538,
        "longitude": -74.531250,
        "disappear_time": 1234
    }
}
"""    

def email_with_alternatives(headers, text=None, html=None):
    
    if text is None and html is None:
        raise ValueError(
            "neither `text` nor `html` content was given for "
            "sending the email")
    
    if not ("To" in headers and
            "From" in headers and
            "Subject" in headers):
        raise ValueError(
            "`headers` dict must include at least all of "
            "'To', 'From' and 'Subject' keys")

    # Create the root message and fill in the from, to, and subject headers
    msg_root = MIMEMultipart('related')
    for name, value in headers.items():
        msg_root[name] = isinstance(value, list) and ', '.join(value) or value
    msg_root.preamble = 'This is a multi-part message in MIME format.'

    # Encapsulate the plain and HTML versions of the message body in an
    # 'alternative' part, so message agents can decide which they want
    # to display.
    msg_alternative = MIMEMultipart('alternative')
    msg_root.attach(msg_alternative)

    # Attach HTML and text alternatives.
    if text:
        msg_text = MIMEText(text.encode('utf-8'), _charset='utf-8')
        msg_alternative.attach(msg_text)
    if html:
        msg_text = MIMEText(html.encode('utf-8'), 'html', _charset='utf-8')
        msg_alternative.attach(msg_text)

    to_addrs = headers["To"] \
        + headers.get("Cc", []) \
        + headers.get("Bcc", [])
    from_addr = msg_root["From"]
    
    smtp = smtplib.SMTP(config["smtp_host"],
                        config["smtp_port"])
    smtp.ehlo()
    smtp.starttls()
    smtp.ehlo()
    smtp.login(config["smtp_auth_user"],
               config["smtp_auth_pass"])
    smtp.sendmail(from_addr, to_addrs, msg_root.as_string())
    smtp.close()

def want(pid):
    if pid in WANTED:
        return True
    else:
        return any(want(x) for x in POKEDEX[pid]["evolves_to"])

class MonHandler(tornado.web.RequestHandler):

    def post(self):
        content = tornado.escape.json_decode(self.request.body)
        if content['type'] != 'pokemon':
            return

        species = content['message']['pokemon_id']
        species_name = POKEDEX[int(species)]["name"]

        print "{name},{latitude},{longitude},{disappear_time}".format(name=species_name, **content['message'])

        if not want(int(species)):
            return

        encounter = content['message']["encounter_id"]
        # Don't send duplicate notifications
        if encounter in encounters:
            return
        encounters.add(encounter)

        headers = config['headers']
        headers['Subject'] = species_name

        despawn = datetime.fromtimestamp(int(content['message']['disappear_time']))
        despawn = utc.localize(despawn).astimezone(mytz)
        despawn = despawn.strftime('%I:%M:%S')

        text = "{0}\n\nhttp://maps.google.com/maps?q={2},{3} \n\n {1}".format(
            species_name, despawn, content['message']['latitude'], content['message']['longitude'])
        html = '<b>{0}</b> until {1}<br/><img width="600" src="http://maps.googleapis.com/maps/api/staticmap?center={2},{3}&zoom=17&scale=false&size=600x300&maptype=roadmap&key={4}&format=png&visual_refresh=true&markers=size:mid%7Ccolor:0xff0000%7Clabel:1%7C{2},{3}" alt="{0}">'.format(
            species_name, despawn, content['message']['latitude'], content['message']['longitude'],
            config['gmaps_api_key']
        )
        email_with_alternatives(headers, text, html)
        self.write(species_name)


def make_app():
    return tornado.web.Application([
        (r"/pokemon", MonHandler),
    ], autoreload=True)

if __name__ == "__main__":
    app = make_app()
    app.listen(5000)
    tornado.ioloop.IOLoop.current().start()
