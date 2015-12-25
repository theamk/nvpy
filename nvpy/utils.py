# nvPY: cross-platform note-taking app with simplenote syncing
# copyright 2012 by Charl P. Botha <cpbotha@vxlabs.com>
# new BSD license

import datetime
import random
import re
import string
import urllib2

# first line with non-whitespace should be the title
note_title_re = re.compile('\s*(.*)\n?')


def generate_random_key():
    """Generate random 30 digit (15 byte) hex string.

    stackoverflow question 2782229
    """
    return '%030x' % (random.randrange(256 ** 15),)


def get_note_title(note):
    mo = note_title_re.match(note.get('content', ''))
    if mo:
        return mo.groups()[0]
    else:
        return ''


def get_note_title_file(note):
    mo = note_title_re.match(note.get('content', ''))
    if mo:
        fn = mo.groups()[0]
        fn = fn.replace(' ', '_')
        fn = fn.replace('/', '_')
        if not fn:
            return ''

        if isinstance(fn, str):
            fn = unicode(fn, 'utf-8')
        else:
            fn = unicode(fn)

        if note_markdown(note):
            fn += '.mkdn'
        else:
            fn += '.txt'

        return fn
    else:
        return ''


def human_date(timestamp):
    """
    Given a timestamp, return pretty human format representation.

    For example, if timestamp is:
    * today, then do "15:11"
    * else if it is this year, then do "Aug 4"
    * else do "Dec 11, 2011"
    """

    # this will also give us timestamp in the local timezone
    dt = datetime.datetime.fromtimestamp(timestamp)
    # this returns localtime
    now = datetime.datetime.now()

    if dt.date() == now.date():
        # today: 15:11
        return dt.strftime('%H:%M')

    elif dt.year == now.year:
        # this year: Aug 6
        # format code %d unfortunately 0-pads
        return dt.strftime('%b') + ' ' + str(dt.day)

    else:
        # not today or this year, so we do "Dec 11, 2011"
        return '%s %d, %d' % (dt.strftime('%b'), dt.day, dt.year)


def note_pinned(n):
    asystags = n.get('systemtags', 0)
    # no systemtag at all
    if not asystags:
        return 0

    if 'pinned' in asystags:
        return 1
    else:
        return 0


def note_markdown(n):
    asystags = n.get('systemtags', 0)
    # no systemtag at all
    if not asystags:
        return 0

    if 'markdown' in asystags:
        return 1
    else:
        return 0

tags_illegal_chars = re.compile(r'[\s]')


def sanitise_tags(tags):
    """
    Given a string containing comma-separated tags, sanitise and return a list of string tags.

    The simplenote API doesn't allow for spaces, so we strip those out.

    @param tags: Comma-separated tags, one string.
    @returns: List of strings.
    """

    # hack out all kinds of whitespace, then split on ,
    # if you run into more illegal characters (simplenote does not want to sync them)
    # add them to the regular expression above.
    illegals_removed = tags_illegal_chars.sub('', tags)
    if len(illegals_removed) == 0:
        # special case for empty string ''
        # split turns that into [''], which is not valid
        return []

    else:
        return illegals_removed.split(',')


def get_note_sort_key_func(config):
    """Return a function which takes a note object (as received from server),
    and returns a sort order key
    """

    if config.pinned_ontop == 0:
        # always pretend note is not pinned
        pinned_func = lambda note: 0
    else:
        pinned_func = note_pinned

    if config.sort_mode == 0:
        # sort alphabetically on title
        return lambda note: (-pinned_func(note),
                             get_note_title(note))
    elif config.sort_mode == 2:
        # sort by creation date
        return lambda note: (-pinned_func(note),
                             -float(note.get('createdate', 0)))
    else:
        # sort by modification date
        return lambda note: (-pinned_func(note),
                             -float(note.get('modifydate', 0)))

def get_kvo_sort_key_func(config):
    """Returns a function with takes KeyValueObject with note= parameter
    and returns a sort order key"""
    note_func = get_note_sort_key_func(config)
    return lambda o: note_func(o.note)

class KeyValueObject:
    """Store key=value pairs in this object and retrieve with o.key.

    You should also be able to do MiscObject(**your_dict) for the same effect.
    """

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class SubjectMixin:
    """Maintain a list of callables for each event type.

    We follow the convention action:object, e.g. change:entry.
    """

    def __init__(self):
        self.observers = {}
        self.mutes = {}

    def add_observer(self, evt_type, o):
        if evt_type not in self.observers:
            self.observers[evt_type] = [o]

        elif o not in self.observers[evt_type]:
            self.observers[evt_type].append(o)

    def notify_observers(self, evt_type, evt):
        if evt_type in self.mutes or evt_type not in self.observers:
            return

        for o in self.observers[evt_type]:
            # invoke observers with ourselves as first param
            o(self, evt_type, evt)

    def mute(self, evt_type):
        self.mutes[evt_type] = True

    def unmute(self, evt_type):
        if evt_type in self.mutes:
            del self.mutes[evt_type]
