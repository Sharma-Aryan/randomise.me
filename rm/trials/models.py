"""
MODELS for trials we're running
"""
import datetime
import random

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.db import models
import letter

from rm import exceptions
from rm.trials import managers

td = lambda: datetime.date.today()
POSTIE = letter.DjangoPostman()

class Trial(models.Model):
    """
    An individual trial that we are running.
    """
    SCORE  = 'sc'
    BINARY = 'bi'
    COUNT  = 'co'
    STYLE_CHOICES = (
        (SCORE,  'Score'),
        (BINARY, 'Binary'),
        (COUNT,  'Count')
        )

    HELP_URL = """This allows you to set a human-friendly url for your trial
so you can share nice links to it. If your url is set to 'awesome-trial' then
your trial will be available from randomise.me/awesome-trial. Valid characters
in your URL are letters, numbers underscores and hyphens. If you're into
regex, that's ([a-zA-Z0-9_-]+). You don't have to set a URL now, you can always
come back to it later. (Not implemented yet)"""
    HELP_DESC = """This is the explanatory text about your trial that will be
publically visible."""
    HELP_A = """These are the instructions that will be sent to Group A."""
    HELP_B = """These are the instructions that will be sent to Group B."""
    HELP_START = "The date you would like your trial to start"
    HELP_FINISH = "The date you would like your trial to finish"

    name              = models.CharField(max_length=200)
    # TODO Validate and implement this.
    url               = models.CharField(max_length=120,
                                         help_text=HELP_URL, blank=True, null=True)
    private           = models.BooleanField(default=False)
    style             = models.CharField(max_length=2, choices=STYLE_CHOICES)
    description       = models.TextField(help_text=HELP_DESC)
    group_a           = models.TextField(help_text=HELP_A)
    group_b           = models.TextField(help_text=HELP_B)
    min_participants  = models.IntegerField()
    max_participants  = models.IntegerField()
    group_a_expected  = models.IntegerField(blank=True, null=True)
    group_b_impressed = models.IntegerField(blank=True, null=True)
    start_date        = models.DateField(help_text=HELP_START)
    finish_date       = models.DateField(help_text=HELP_FINISH)
    finished          = models.BooleanField(default=False, editable=False)
    owner             = models.ForeignKey(User)
    featured          = models.BooleanField(default=False)
    recruiting        = models.BooleanField(default=True)

    objects = managers.RmTrialManager()

    def __unicode__(self):
        """
        Nice printing representation
        """
        return '<{0}>'.format(self.name)

    def get_absolute_url(self):
        return reverse('trial-detail', kwargs={'pk': self.pk})

    def save(self):
        """
        Check for recruiting status

        Return: None
        Exceptions: None
        """
        self.recruiting = self.can_join()
        return super(Trial, self).save()

    def results(self):
        """
        Return the results of this trial

        Return: dict
        Exceptions: None
        """
        return [dict(name='Group A', avg=random.randrange(1, 100)),
                dict(name='Group B', avg=random.randrange(1, 100))]


    def time_remaining(self):
        """
        How much time is between now and the end of the trial?

        Return: timedelta or str
        Exceptions: None
        """
        if self.finish_date < td():
            return 'Trial finished'
        return self.finish_date - td()

    def can_join(self):
        """
        Predicate method to determine whether users are able to
        join this trial.

        We decide that a trial is unjoinable if it's finish date has
        passed, or if it's max participants limit has been met.
        """
        if self.finish_date < td():
            return False
        if self.participant_set.count() >= self.max_participants:
            return False
        return True

    def ensure_groups(self):
        """
        Ensure that the groups for this trial exist.
        """
        groupa = Group.objects.get_or_create(trial=self, name='a')[0]
        groupb = Group.objects.get_or_create(trial=self, name='b')[0]
        return groupa, groupb

    def join(self, user):
        """
        Add a user to our trial.

        Make sure that the trial has groups, then randomly assign USER
        to one of those groups.

        Ensure that we haven't gone over the max_participants level,
        raising TooManyParticipantsError if we have.

        Ensure that this user hasn't already joined the trial, raising
        AlreadyJoinedError if we have.

        Ensure that this user doesn't own the trial, raising
        TrialOwnerError if they do.

        Ensure that this trial isn't already finished, raising
        TrialFinishedError if it is.

        If nobody has joined yet, we go to Group A, else Group A if
        the groups are equal, else Group B.
        """
        if self.owner == user:
            raise exceptions.TrialOwnerError()
        today = datetime.date.today()
        if self.finish_date < today:
            raise exceptions.TrialFinishedError()
        if Participant.objects.filter(trial=self, user=user).count() > 0:
            raise exceptions.AlreadyJoinedError()
        if self.participant_set.count() >= self.max_participants:
            raise exceptions.TooManyParticipantsError()
        Participant(trial=self, user=user).save()
        return

    def randomise(self):
        """
        Randomise the participants of this trial.

        If we have already randomised the participants, raise AlreadyRandomisedError.

        Return: None
        Exceptions: AlreadyRandomisedError
        """
        if self.participant_set.filter(group__isnull=False).count() > 0:
            raise exceptions.AlreadyRandomisedError()
        groupa, groupb = self.ensure_groups()
        for participant in self.participant_set.all():
            participant.group = random.choice([groupa, groupb])
            participant.save()
        return

    def send_instructions(self):
        """
        Email the participants of this trial with their instructions.

        Return: None
        Exceptions:
            - TrialFinishedError: The trial has finished
            - TrialNotStartedError: The trial is yet to start
        """
        if self.start_date is not None and self.start_date > td():
            raise exceptions.TrialNotStartedError()
        if self.finish_date is not None and self.finish_date < td():
            raise exceptions.TrialFinishedError()
        for participant in self.participant_set.all():
            participant.send_instructions()
        return


class Variable(models.Model):
    """
    A variable that we are reporting on
    """
    SCORE  = 'sc'
    BINARY = 'bi'
    COUNT  = 'co'

    STYLE_CHOICES = (
        (SCORE,  'Score'),
        (BINARY, 'Binary'),
        (COUNT,  'Count')
        )

    trial = models.ForeignKey(Trial)
    name  = models.CharField(max_length=200)
    style = models.CharField(max_length=2, choices=STYLE_CHOICES)

    def __unicode__(self):
        return '<Variable {0} ({1})>'.format(self.name, self.style)


class Group(models.Model):
    """
    The randomised groups of participants, automatically
    created for our trials
    """
    NAME_CHOICES = (
        ('A', 'Group A'),
        ('B', 'Group B')
        )
    trial = models.ForeignKey(Trial)
    name  = models.CharField(max_length=1, choices=NAME_CHOICES)


class Participant(models.Model):
    """
    A participant in a trial
    """
    user  = models.ForeignKey(User)
    trial = models.ForeignKey(Trial)
    group = models.ForeignKey(Group, blank=True, null=True)

    def __unicode__(self):
        """
        Pretty printin'
        """
        return '<{0} - {1} ({2})>'.format(self.user, self.trial, self.group)

    def send_instructions(self):
        """
        Email the participant their instructions for this trial.

        If the participant does not have an email address, raise an error.

        Return: None
        Exceptions: NoEmailError
        """
        if not self.user.email:
            raise exceptions.NoEmailError()

        subject = 'Randomise.me - instructions for {0}'.format(self.trial.name)
        instructions = self.group.name == 'A' and self.trial.group_a or self.trial.group_b

        class Message(letter.Letter):
            Postie   = POSTIE

            From     = settings.DEFAULT_FROM_EMAIL
            To       = self.user.email
            Subject  = subject
            Template = 'email/rm_instructions'
            Context  = {
                'href'        : settings.DEFAULT_DOMAIN + self.trial.get_absolute_url(),
                'instructions': instructions,
                'name'        : self.trial.name
                }

        Message.send()

        return


class Report(models.Model):
    "A report of a single datapoint for a trial"
    GROUP_CHOICES = (
        ('A', 'Group A'),
        ('B', 'Group B')
        )

    trial = models.ForeignKey(Trial)
    group = models.CharField(max_length=1, choices=GROUP_CHOICES)
    date  = models.DateField()
    score = models.IntegerField()

    def get_absolute_url(self):
        return reverse('trial-detail', kwargs={'pk': self.trial.pk})


class SingleUserTrial(models.Model):
    """
    A trial that a user runs on themselves.
    These will form part of the on-boarding process in the fullness of time.
    """
    HELP_INTERVAL = """This is the frequency with which you're going to
record data in the trial. It lets us know how often to allocate you into
one of the groups in the trial.
"""
    HELP_START = """This is the date on which the trial will start."""
    HELP_FINISH = """This is the date on which the trial will finish."""
    HELP_QUEST = """It helps to have a good description of the question
you're trying to answer by running this trial. A good example would be
'Does drinking Tea make you wee?'"""
    HELP_A = """These are the instructions that will be sent when you're in Group A."""
    HELP_B = """These are the instructions that will be sent when you're in Group B."""
    HELP_VAR = """This is the name of the variable you'll be measuring. It's
useful for us when we draw you pretty graphs. If you were counting the number of
wees you took on a given day, then a good value here would be 'wees'"""

    DAILY   = 'da'
    WEEKLY  = 'we'
    MONTHLY = 'mo'
    CHOICES_INTERVAL = (
        (DAILY, 'Daily'),
        )

    owner       = models.ForeignKey(User)
    name        = models.CharField(max_length=200)
    # This is incredibly useful, but Later :)
    # interval    = models.CharField(max_length=2, choices=CHOICES_INTERVAL,
    #                                help_text=HELP_INTERVAL)
    start_date  = models.DateField(help_text=HELP_START)
    finish_date = models.DateField(help_text=HELP_FINISH)
    question    = models.TextField(help_text=HELP_QUEST)
    variable    = models.CharField(max_length=200, help_text=HELP_VAR)
    group_a     = models.TextField(help_text=HELP_A)
    group_b     = models.TextField(help_text=HELP_B)

    objects = managers.SingleUserTrialManager()

    def __unicode__(self):
        """
        Pretty printin'
        """
        return '<Single User Trial {0} ({1})>'.format(self.name, self.owner)

    def get_absolute_url(self):
        return reverse('user-trial-detail', kwargs={'pk': self.pk})

    @property
    def started(self):
        """
        Property to determine whether this trial has started or not.

        Return: bool
        Exceptions: None
        """
        if self.start_date is None:
            return False
        if self.start_date <= datetime.date.today():
            return True
        return False

    @property
    def finished(self):
        """
        Predicate property to determine whether this trial is finished.

        Return: bool
        Exceptions: None
        """
        if self.finish_date < td():
            return True
        return False

    @property
    def active(self):
        """
        Property to determine whether this trial is active today.

        Return: bool
        Exceptions: None
        """
        if not self.start_date or not self.finish_date:
            return False
        if self.start_date <= td() and self.finish_date >= td():
            return True
        return False

    def results(self):
        """
        Return the results of this trial

        Return: dict
        Exceptions: None
        """
        a = self.singleuserreport_set.filter(group='A').aggregate(models.Avg('score'))['score__avg']
        b = self.singleuserreport_set.filter(group='B').aggregate(models.Avg('score'))['score__avg']
        return [dict(name='Group A', avg=a), dict(name='Group B', avg=b)]

    def _out_of_bounds(self):
        """
        Helper method for repeated out of bounds logic.
        """
        if self.start_date is not None and self.start_date > td():
            raise exceptions.TrialNotStartedError()
        if self.finish_date is not None and self.finish_date < td():
            raise exceptions.TrialFinishedError()
        return

    def _email_instructions(self, instructions, date):
        """
        Given a set of INSTRUCTIONS for a DATE, email them to
        this trial's Owner.

        If this trial's owner has no email, raise

        Arguments:
        - `instructions`: str
        - `date`: Date

        Return: None
        Exceptions: NoEmailError
        """
        if not self.owner.email:
            raise exceptions.NoEmailError()

        date = date.strftime('%d/%m/%Y')
        subject = 'Randomise.me - instructions for {0} {1}'.format(
            self.name, date)

        class Message(letter.Letter):
            Postie   = POSTIE

            From     = settings.DEFAULT_FROM_EMAIL
            To       = self.owner.email
            Subject  = subject
            Template = 'email/singleuser_instructions'
            Context  = {
                'href'        : settings.DEFAULT_DOMAIN + self.get_absolute_url(),
                'instructions': instructions,
                'date'        : date,
                'name'        : self.name
                }

        Message.send()
        return

    def send_instructions(self):
        """
        Email the owner of this trial with their instructions for today.

        Return: None
        Exceptions:
            - TrialFinishedError: The trial has finished
            - TrialNotStartedError: The trial is yet to start
        """
        self._out_of_bounds()
        self._email_instructions(self.instructions_on(td()), td())
        return

    def instructions_on(self, date):
        """
        Find the instructions for this trial on DATE.

        if the date is out of bounds for this trial, raise an error.

        Arguments:
        - `date`: Date

        Return: str
        Exceptions:
                   TrialNotStartedError
                   TrialFinishedError
        """
        self._out_of_bounds()
        return SingleUserAllocation.instructions_on(self, date)

    def instructions_today(self):
        """
        Find the instructions for this trial today.

        Return: str
        Exceptions:
        """
        return self.instructions_on(td())




class SingleUserAllocation(models.Model):
    """
    The daily allocation of a user into a group
    """
    GROUP_CHOICES = (
        ('A', 'Group A'),
        ('B', 'Group B')
        )

    trial = models.ForeignKey(SingleUserTrial)
    date  = models.DateField()
    group = models.CharField(max_length=1, choices=GROUP_CHOICES)

    @staticmethod
    def instructions_on(trial, date):
        """
        Find the instructions for TRIAL on DATE.
        If no allocation has been conducted, do that now.

        Arguments:
        - `trial`: SingleUserTrial
        - `date`: Date

        Return: str
        Exceptions: None
        """
        allocation = SingleUserAllocation.objects.get_or_create(trial=trial, date=date)[0]
        if not allocation.group:
            allocation.randomise()
            allocation.save()

        if allocation.group == 'A':
            return trial.group_a
        elif allocation.group == 'B':
            return trial.group_b
        return

    def randomise(self):
        """
        Conduct our randomisation for this trial on this day.

        If the trial has already been randomised fo this day, raise
        AlreadyRandomisedError

        Return: None
        Exceptions: AlreadyRandomisedError
        """
        if self.group == '':
            self.group = random.choice(['A', 'B'])
            return
        raise exceptions.AlreadyRandomisedError()


class SingleUserReport(models.Model):
    """
    A report of a value for a day in a trial.
    """
    GROUP_CHOICES = (
        ('A', 'Group A'),
        ('B', 'Group B')
        )

    trial = models.ForeignKey(SingleUserTrial)
    group = models.CharField(max_length=1, choices=GROUP_CHOICES)
    date  = models.DateField()
    score = models.IntegerField()

    def get_absolute_url(self):
        return reverse('user-trial-detail', kwargs={'pk': self.trial.pk})
