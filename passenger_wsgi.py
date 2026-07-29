"""Point d'entrée Passenger — o2switch / cPanel « Setup Python App ».

Passenger cherche une variable nommée `application`. On y expose l'app Flask.
Dans cPanel :
  - Application startup file : passenger_wsgi.py
  - Application Entry point  : application
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from server import app as application  # noqa: E402
