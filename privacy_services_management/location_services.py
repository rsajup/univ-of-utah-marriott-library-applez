import os
import subprocess
import universal

try:
    from management_tools.plist_editor import PlistEditor
    from management_tools.app_info import AppInfo
except ImportError as e:
    print("You need the 'Management Tools' module to be installed first.")
    print(
        "https://github.com/univ-of-utah-marriott-library-apple/" +
        "management_tools")
    raise e

class LSEdit(object):
    '''A class to help with editing Location Services. This ought to be used
    in a 'with' statement to ensure proper updating of the locationd system e.g.

    with LSEdit() as e:
        # do some stuff to the database
        e.foo()
    # do more stuff to other things
    bar(baz)
    '''

    def __init__(self, logger=None):
        # Set the logger for output.
        if logger:
            self.logger = logger
        else:
            self.logger = universal.NullOutput()

        # Only root may modify the Location Services system.
        if os.geteuid() != 0:
            raise RuntimeError("Must be root to modify Location Services!")

        # Check the version of OS X before continuing; only Darwin versions 12
        # and above support the TCC database system.
        try:
            version = int(os.uname()[2].split('.')[0])
        except:
            raise RuntimeError("Could not acquire the OS X version.")
        if version < 10:
            raise RuntimeError(
                "Location Services is not supported in this version of OS X.")
        self.version = version

        # Disable the locationd launchd item. (Changes will not be properly
        # cached if this is not done.)
        self.__disable()
        # This is where the applications' authorizations are stored.
        self.plist = PlistEditor('/var/db/locationd/clients')
        self.logger.info(
            "Modifying service 'location' at '" + self.plist.path + "'.")

    def __enter__(self):
        return self

    def insert(self, app):
        '''Insert 'app' and enable it for Location Services.

        app - an application identifier (bid, short name, location, etc.)
        '''

        # If no application is given, then we're modifying the global Location
        # Services system.
        if not app:
            self.logger.info("Enabling service 'location' globally.")
            enable_global(True, self.version, self.logger)
            self.logger.info("Globally enabled successfully.")
            return

        app = AppInfo(app)

        # Verbosity!
        self.logger.info("Inserting '" + app.bid + "' into service 'location'...")

        # This is used for... something. Don't know what, but it's necessary.
        requirement = (
            "identifier \"" + app.bid + "\" and anchor " +
            app.bid.split('.')[1]
        )

        # Write the changes to the locationd plist.
        result = 0
        result += self.plist.dict_add(app.bid, "Authorized", "TRUE", "bool")
        result += self.plist.dict_add(app.bid, "BundleID", app.bid)
        result += self.plist.dict_add(app.bid, "BundleId", app.bid)
        result += self.plist.dict_add(app.bid, "BundlePath", app.path)
        result += self.plist.dict_add(app.bid, "Executable", app.executable)
        result += self.plist.dict_add(app.bid, "Registered", app.executable)
        result += self.plist.dict_add(app.bid, "Hide", 0, "int")
        result += self.plist.dict_add(app.bid, "Requirement", requirement)
        result += self.plist.dict_add(app.bid, "Whitelisted", "FALSE", "bool")
        if result:
            # Clearly there was an error...
            raise RuntimeError("Failed to insert " + app.name + ".")
        self.logger.info("Inserted successfully.")

    def remove(self, app):
        '''Remove 'app' from Location Services.

        app - an application identifier
        '''

        # If no application is given, then we're modifying the global Location
        # Services system.
        if not app:
            self.logger.info("Disabling service 'location' globally...")
            enable_global(False, self.version, self.logger)
            self.logger.info("Globally disabled successfully.")
            return

        app = AppInfo(app)

        # Verbosity
        self.logger.info("Removing '" + app.bid + "' from service 'location'...")

        # Otherwise, just delete its entry in the plist.
        result = self.plist.delete(app.bid)
        if result:
            raise RuntimeError("Failed to remove " + app.name + ".")
        self.logger.info("Removed successfully.")

    def disable(self, application):
        '''Leave (or insert) an application into the Location Services plist,
        but mark the application as being disallowed from utilizing Location
        Services.

        app - an application identifier
        '''

        # If no application is given, then we're modifying the global Location
        # Services system.
        if not application:
            self.logger.info("Disabling service 'location' globally...")
            enable_global(False, self.version, self.logger)
            self.logger.info("Globally disabled successfully.")
            return

        app = AppInfo(application)

        # Verboseness
        self.logger.info("Disabling '" + app.bid + "' in service 'location'...")

        # If the application isn't already in locationd, add it.
        if not self.plist.read(app.bid):
            self.insert(app.bid)

        # Then deauthorize the application.
        result = self.plist.dict_add(app.bid, "Authorized", "FALSE", "bool")
        if result:
            raise RuntimeError("Failed to disable " + app.name + ".")
        self.logger.info("Disabled successfully.")

    def __exit__(self, type, value, traceback):
        # Make sure that the locationd launchd item is reactivated.
        self.__enable()

    def __enable(self):
        enable()
        self.logger.info("Enabled locationd system.")

    def __disable(self):
        disable()
        self.logger.info(
            "Disabled locationd system. (This is normal. DON'T PANIC.)")

def enable_global(enable, version, logger=None):
    '''Enables or disables the Location Services system globally.'''

    if not logger:
        logger = universal.NullOutput()

    try:
        value = int(enable)
    except:
        raise ValueError("'" + str(enable) + "' not a boolean.")

    uuid = get_uuid()
    ls_dir = '/var/db/locationd/Library/Preferences/ByHost/'
    ls_plist = ls_dir + 'com.apple.locationd.' + str(uuid) + '.plist'
    logger.info("Modifying global values in '" + ls_plist + "'.")

    if not os.path.isfile(ls_plist):
        ls_plist = None
        potentials = [
            x.lstrip('com.apple.locationd.').rstrip('.plist')
            for x in os.listdir(ls_dir)
            if str(x).endswith('.plist')
            and str(x).startswith('com.apple.locationd.')
        ]
        potentials = [x for x in potentials if not x.find('.') >= 0]
        if len(potentials) > 1:
            for id in potentials:
                if uuid == id or uuid.lower() == id or uuid.upper() == id:
                    ls_plist = (
                        ls_dir + 'com.apple.locationd.' + id + '.plist'
                    )
                    break
                for part in uuid.split('-'):
                    if part == id or part.lower() == id or part.upper() == id:
                        ls_plist = (
                            ls_dir + 'com.apple.locationd.' + id + '.plist'
                        )
                        break
                if ls_plist:
                    break
        elif len(potentials) == 1:
            ls_plist = (
                ls_dir + 'com.apple.locationd.' + potentials[0] + '.plist'
            )
        else:
            raise RuntimeError(
                "No Location Services global property list found at '" +
                ls_plist + "'.")

    if ls_plist:
        ls_plist = PlistEditor(ls_plist)
        if version < 14:
            ls_plist.write("LocationServicesEnabled", value, "int")
        else:
            ls_plist.write("LocationServicesEnabledIn7.0", value, "int")
    else:
        raise RuntimeError(
            "Could not locate Location Services plist file at '" +
            ls_plist + "'.")

def get_uuid():
    '''Acquire the UUID of the hardware.'''

    ioreg = [
        '/usr/sbin/ioreg',
        '-rd1',
        '-c',
        'IOPlatformExpertDevice'
    ]

    uuid = subprocess.check_output(ioreg, stderr=subprocess.STDOUT).split('\n')
    uuid = [x for x in uuid if x.find('UUID') >= 0]

    if len(uuid) != 1:
        raise RuntimeError("Could not find a unique UUID.")

    return uuid[0].lstrip().rstrip('"').split('= "')[1]

def enable():
    '''Fix permissions for the _locationd user, then load the locationd
    launchd item.'''

    chown = [
        '/usr/sbin/chown',
        '-R',
        '_locationd:_locationd',
        '/var/db/locationd'
    ]

    result = subprocess.call(
        chown,
        stderr=subprocess.STDOUT,
        stdout=open(os.devnull, 'w')
    )
    if result != 0:
        raise RuntimeError("Unable to repair permissions: '/var/db/locationd'!")

    launchctl = [
        '/bin/launchctl',
        'load',
        '/System/Library/LaunchDaemons/com.apple.locationd.plist'
    ]

    output = subprocess.check_output(
        launchctl,
        stderr=subprocess.STDOUT
    ).strip('\n')

    return output

def disable():
    '''Unload the locationd launchd item.'''

    launchctl = [
        '/bin/launchctl',
        'unload',
        '/System/Library/LaunchDaemons/com.apple.locationd.plist'
    ]

    output = subprocess.check_output(
        launchctl,
        stderr=subprocess.STDOUT
    ).strip('\n')

    return output
