from ovs.db.idl import Transaction

# Ovsdb connection states and defaults
OVSDB_STATUS_DISCONNECTED = 1
OVSDB_STATUS_CONNECTED = 2
OVSDB_DEFAULT_CONNECTION_TIMEOUT = 1.0

# All IDL Transaction states
UNCOMMITTED = Transaction.UNCOMMITTED
UNCHANGED = Transaction.UNCHANGED
INCOMPLETE = Transaction.INCOMPLETE
ABORTED = Transaction.ABORTED
SUCCESS = Transaction.SUCCESS
TRY_AGAIN = Transaction.TRY_AGAIN
NOT_LOCKED = Transaction.NOT_LOCKED
ERROR = Transaction.ERROR

# Ovsdb schema constants
OVSDB_SCHEMA_TOP_LEVEL_TABLE = 'Open_vSwitch'
OVSDB_SCHEMA_TOP_LEVEL_URL_PATH = 'system'
