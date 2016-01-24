##                ##
# TriviaBot Config #
##                 ##

# List of admin nicknames and the single game channel
ADMINS = ['admin', 'Bob']
GAME_CHANNEL = '#triviachannel'

# Folder locations
Q_DIR = './questions/'
SAVE_DIR = './savedata/'

# Bot's info
DEFAULT_NICK = 'TriviaBot'
DEFAULT_NAME = 'Trivia Bot'
DEFAULT_MODES = 'iB'
DEFAULT_QUIT = 'This is triviabot, signing off.'
IDENT_PASS = 'password'

# Trivia Speed
WAIT_INTERVAL = 15
LINE_RATE = 0.4

# Connection info
SERVER = 'irc.freenode.net'
SERVER_PORT = 6667
# Increase this if you have a very poor connection
TIMEOUT = 30
# If not using SSL, leave this commented out
#SERVER_TYPE = 'ssl'
# If you need to bind to a specific address or port, uncomment the following
# Defaults are to use a random port and any IPv4 interface
#BIND_PORT = 43000
#BIND_ADDR = '0.0.0.0'
