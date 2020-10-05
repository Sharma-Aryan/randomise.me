# Real time clock
import time
while True:
    from datetime import datetime
    now = datetime.now()
    print ("%s/%s/%s %s:%s:%s" % (now.month,now.day,now.year,now.hour,now.minute,now.second))
    time.sleep(1)
This is the source code for http://randomiseme.org

### Contributing

Development environment as a vagrant VM available [here](https://github.com/openhealthcare/developer)

    $ vagrant ssh
    $ workon rm
    $ python manage.py runserver 0.0.0.0:8000

Superuser already created: super/super1

Source code mounted to host at ./src/randomise.me
