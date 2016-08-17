#!/usr/bin/python2
# Copyright (C) 2013 Joe Rawson
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Need to load the scores, if they exist, and connect to irc, displaying
# a welcome message.
#
# Scores should be kept in a class which will hold a nick -> score dict
# object, and at the end of every question will dump the dict to json
# where it can be loaded from. This might get weird if people start using
# weird nicks, but we'll cross that road when we get to it.
#
# irc connection should be a class, and we should use twisted. We don't
# really care if people come and go, since everyone in the channel is
# playing. Should handle this like karma. Watch all traffic, and if
# someone blurts out a string that matches the answer, they get the points.
# If they haven't scored before, add them to the scoreboard and give them
# their points, else, add their points to their total. Then dump the json.
#
# This bot requires there to be a ../questions/ directory with text files
# in it. These files are named after there genres, so "80s Films.txt"
# and the like. While the bot is running, it will randomly choose a
# file from this directory, open it, randomly choose a line, which is
# a question*answer pair, then load that into a structure to be asked.
#
# Once the question is loaded, the bot will ask the IRC channel the
# question, wait a period of time, show a character, then ask the question
# again.
#
# The bot should respond to /msgs, so that users can check their scores,
# and admins can give admin commands, like die, show all scores, edit
# player scores, etc. Commands should be easy to implement.
#
# Every so often between questions the bot should list the top ranked
# players, wait some, then continue.
#

import json
from os import execl, listdir, path, makedirs
from random import choice, randint
import re
import sys

from twisted.words.protocols import irc
from twisted.internet import reactor
from twisted.internet import ssl
from twisted.internet.protocol import ClientFactory
from twisted.internet.task import LoopingCall

from lib.answer import Answer

import config


class triviabot(irc.IRCClient):
    '''
    This is the irc bot portion of the trivia bot.

    It implements the whole program so is kinda big. The algorithm is
    implemented by a series of callbacks, initiated by an admin on the
    server.
    '''
    def __init__(self):
        self._answer = Answer()
        self._question = ''
        self._scores = {}
        self._userlist = {}
        self._clue_number = 0
        self._admins = list(config.ADMINS)
        self._game_channel = config.GAME_CHANNEL
        self._current_points = 5
        self._questions_dir = config.Q_DIR
        self._lc = LoopingCall(self._play_game)
        self._restarting = False
        self._quit = False
        self._load_game()
        self._votes = 0
        self._voters = []
        self._no_plays = 0

    def _get_nickname(self):
        return self.factory.nickname

    nickname = property(_get_nickname)

    def _get_realname(self):
        return self.factory.realname

    realname = property(_get_realname)

    def _get_lineRate(self):
        return self.factory.lineRate

    lineRate = property(_get_lineRate)

    def _gmsg(self, msg):
        """
        Write a message to the channel playing the trivia game.
        """
        self.msg(self._game_channel, msg)

    def _play_game(self):
        '''
        Implements the main loop of the game.
        '''
        self._points = {0: 100,
                        1: 75,
                        2: 50,
                        3: 25
                        }
        self._cluelabels= {0: 'Clue:',
                           1: '2nd Clue:',
                           2: '3rd Clue:',
                           3: 'Final Clue:'
                           }
        if self._clue_number == 0:
            self._votes = 0
            self._voters = []
            self._get_new_question()
            self._current_points = self._points[self._clue_number]
            # Blank line.
            self._gmsg("")
            self._gmsg("Next question:")
            self._gmsg(self._question)
            self._gmsg("%s %s  Points: %d" % (self._cluelabels[self._clue_number],
                       self._answer.current_clue(), self._current_points))
            self._clue_number += 1
        # we must be somewhere in between
        elif self._clue_number < 4:
            self._current_points = self._points[self._clue_number]
            self._gmsg('%s %s  Points: %d' % (self._cluelabels[self._clue_number],
                       self._answer.give_clue(), self._current_points))
            self._clue_number += 1
        # no one must have gotten it.
        else:
            self._gmsg('No one got it. The answer was: %s' %
                       self._answer.answer)
            self._clue_number = 0
            self._no_plays += 1
            # Stop gameplay after 10 questions of no activity
            if (self._no_plays == 10):
                self._gmsg('It appears I am talking to myself now!')
                self._stop()
            else:
                self._get_new_question()

    def irc_RPL_NAMREPLY(self, *nargs):
        '''
        Called when we get a reply to NAMES
        Using this for tracking user modes, in a simplistic manner
        '''
        if (nargs[1][2] != self._game_channel): return
        users = nargs[1][3].split()
        for u in users:
            split = re.split('(\~|\&|\@|\%|\+)', u)
            try:
                mode = split[1]
                user = split[2]
            except IndexError:
                mode = ''
                user = split[0]
            mode = mode.replace('+', 'voice')
            mode = mode.replace('%', 'halfop')
            mode = mode.replace('@', 'op')
            mode = mode.replace('&', 'admin')
            mode = mode.replace('~', 'owner')
            # This is for us joining the channel and re-checking after mode changes
            try:
                self._userlist[user]
                self._userlist['modes'] = (mode,)
            except:
                self._userlist[user] = {}
                self._userlist[user]['wins'] = 0
                self._userlist[user]['modes'] = (mode,)
                self._userlist[user]['strikes'] = 0

    def signedOn(self):
        '''
        Actions to perform on signon to the server.
        '''
        try:
            config.IDENT_PASS
            self.msg('NickServ', 'identify %s' % config.IDENT_PASS)
        except:
            pass
        self.mode(self.nickname, True, config.DEFAULT_MODES)
        print("Signed on as %s." % (self.nickname,))
        self.join(self._game_channel)
        if self.factory.running:
            self._start(None, None, None)
        else:
            self._gmsg('Welcome to %s!' % self._game_channel)
            self._gmsg("For how to use this bot, just say ?help or '%s help'." % self.nickname)

    def joined(self, channel):
        '''
        Callback runs when the bot joins a channel
        A join automatically receives a NAMES reply, for user listing
        '''
        print("Joined %s." % (channel,))
        if (channel != self._game_channel):
            self.leave(channel, 'No!')
            return

    def kickedFrom(self, channel, kicker, message):
        '''
        If we get kicked from gthe game channel,
        attempt to rejoin.
        '''
        print("Kicked from %s by %s: %s" % (channel, kicker, message))
        if (channel != self._game_channel):
            return
        self.join(self._game_channel)

    def userJoined(self, user, channel):
        '''
        Callback for when other users join the channel
        '''
        if channel != self._game_channel: return
        # Add user to userlist, track wins, modes, and strikes of user
        self._userlist[user] = {}
        self._userlist[user]['wins'] = 0
        self._userlist[user]['modes'] = ('',)
        self._userlist[user]['strikes'] = 0
        # If admin, don't send intro notice and op them
        try:
            self._admins.index(user)
            self.mode(channel, True, 'o', user=user)
            self._userlist[user]['modes'].append('op')
        except:
            self.notice(user, "Welcome to %s!" % self._game_channel)
            self.notice(user, "For how to use this bot, just say ?help or '%s help'." % self.nickname)
            if not self.factory.running:
                self.notice(user, "Just say ?start to start the game when you are ready.")

    def userLeft(self, user, channel):
        '''
        Called when a user leaves the game channel
        '''
        if channel != self._game_channel: return
        if user in self._userlist:
            del self._userlist[user]

    def userQuit(self, user, quitMessage):
        '''
        Called when a user quits
        '''
        if channel != self._game_channel: return
        if user in self._userlist:
            del self._userlist[user]

    def userKicked(self, kickee, channel, kicker, message):
        '''
        Called when a user is kicked from the game channel
        '''
        if channel != self._game_channel: return
        if kickee in self._userlist:
            del self._userlist[kickee]

    def userRenamed(self, oldname, newname):
        '''
        Called when a user changes nicknames
        '''
        if oldname in self._userlist:
            self._userlist[newname] = self._userlist.pop(oldname)

    def modeChanged(self, user, channel, set, modes, args):
        '''
        Called when a mode change is seen
        '''
        if channel != self._game_channel: return
        #print('MODE: %s : direction %d : %s and %s' % (user, set, modes, args))
        # Check if 'our' users are part of a mode change, re-run NAMES
        user_change = False
        for u in self._userlist:
            if (u in args):
                user_change = True
                break
        if (user_change == False): return
        self.sendLine('NAMES %s' % channel)

    def privmsg(self, user, channel, msg):
        '''
        Parses out each message and initiates doing the right thing
        with it.
        '''
        user, temp = user.split('!')
        #print(user+" : "+channel+" : "+msg)
        # ignore STATUSMSGs, lazy check
        if (not channel[0] == "#"):
            return
        # need to strip off colors if present.
        try:
            while not msg[0].isalnum() and not msg[0] == '?':
                msg = msg[1:]
        except IndexError:
            return

        # parses each incoming line, and sees if it's a command for the bot.
        try:
            if (msg[0] == "?"):
                command = msg.replace('?', '').split()[0]
                args = msg.replace('?', '').split()[1:]
                self.select_command(command, args, user, channel)
                return
            elif (msg.split()[0].find(self.nickname) == 0):
                command = msg.split()[1]
                args = msg.replace(self.nickname, '').split()[2:]
                self.select_command(command, args, user, channel)
                return
            # if not, try to match the message to the answer.
            else:
                if msg.lower().strip() == self._answer.answer.lower():
                    self._no_plays = 0
                    self._winner(user, channel)
                    self._save_game()
        except:
            return
        # Assuming this is gameplay
        self._no_plays = 0

    def _winner(self, user, channel):
        '''
        Congratulates the winner for guessing correctly and assigns
        points appropriately, then signals that it was guessed.
        '''
        if channel != self._game_channel:
            self.msg(channel,
                     "I'm sorry, answers must be given in the game channel.")
            return
        self._gmsg("%s GOT IT!" % user)
        try:
            self._scores[user] += self._current_points
        except:
            self._scores[user] = self._current_points
        self._gmsg("%s points have been added to your score!" %
                   str(self._current_points))
        self._clue_number = 0
        self._get_new_question()
        self._userlist[user]['wins'] += 1
        if (self._userlist[user]['wins'] == 2):
            self.mode(channel, True, 'v', user=user)
            self._gmsg('Five correct answers! That earns you a voice!')
            self._userlist[user]['modes'].append('voice')
        elif (self._userlist[user]['wins'] == 4):
            self.mode(channel, True, 'h', user=user)
            self._gmsg('Another fifteen correct answers, have some halfops!')
            self._userlist[user]['modes'].append('halfop')

    def ctcpQuery(self, user, channel, msg):
        '''
        Responds to ctcp requests.
        '''
        msg = str(msg[0][0]).lower()
        user = (user.split("!"))[0]
        if (msg == 'action'): return
        print("CTCP from %s : %s" % (user, msg))
        if (msg == 'version'):
            self.notice(user, "CTCP VERSION: Trivia Bot!")
        elif (msg == 'time'):
            self.notice(user, "CTCP TIME: Trivia Time!")
        elif (msg == 'ping'):
            self.notice(user, "CTCP PING: Trivia Pong!")
        else:
            self.notice(user, "Unknown CTCP Query!")

    def _help(self, args, user, channel):
        '''
        Tells people how to use the bot.
        Replies differently if you are an admin or a regular user.
        Only responds to the user since there could be a game in
        progress.
        '''
        try:
            self._admins.index(user)
        except:
            self.notice(user, "Commands: start, stop, score, standings, "
                       "question, clue, help, next, source")
            return
        self.notice(user, "Commands: start, stop, score, standings, "
                   "question, clue, help, next, source")
        self.notice(user, "Admin commands: skip, restart, die, "
                   "set <user> <score>, save")

    def _show_source(self, args, user, channel):
        '''
        Tells people how to use the bot.
        Only responds to the user since there could be a game in
        progress.
        '''
        self.notice(user, 'My source can be found at: '
                   'https://github.com/genius3000/triviabot')
        self.notice(user, 'Original source can be found at: '
                   'https://github.com/rawsonj/triviabot')

    def select_command(self, command, args, user, channel):
        '''
        Callback that responds to commands given to the bot.

        Need to differentiate between priviledged users and regular
        users.
        '''
        # set up command dicts.
        unpriviledged_commands = {'score': self._score,
                                  'help': self._help,
                                  'start': self._start,
                                  'stop': self._stop,
                                  'source': self._show_source,
                                  'standings': self._standings,
                                  'question': self._show_question,
                                  'clue': self._give_clue,
                                  'next': self._next_vote,
                                  }
        priviledged_commands = {'skip': self._next_question,
                                'restart': self._restart,
                                'die': self._die,
                                'set': self._set_user_score,
                                'save': self._save_game,
                                }
        print(command, args, user, channel)
        try:
            self._admins.index(user)
            is_admin = True
        except:
            is_admin = False
        command = command.lower()
        # the following takes care of sorting out functions and
        # priviledges.
        if not is_admin and command in priviledged_commands.keys():
            self.msg(channel, "%s: You don't tell me what to do." % user)
            self._userlist[user]['strikes'] += 1
            if (self._userlist[user]['strikes'] == 5):
                self.kick(channel, user, "You've earned five strikes, be gone!")
            elif ('halfop' in self._userlist[user]['modes']):
                self.mode(channel, False, 'h', user=user)
                self._userlist[user]['modes'].remove('halfop')
            elif ('voice' in self._userlist[user]['modes']):
                self.mode(channel, False, 'v', user=user)
                self._userlist[user]['modes'].remove('voice')
            return
        elif is_admin and command in priviledged_commands.keys():
            priviledged_commands[command](args, user, channel)
        elif command in unpriviledged_commands.keys():
            unpriviledged_commands[command](args, user, channel)
        else:
            self.describe(channel, 'looks at %s oddly.' % user)

    def _next_vote(self, args, user, channel):
        '''Implements user voting for the next question.

        Need to keep track of who voted, and how many votes.

        '''
        if not self._lc.running:
            self._gmsg("We aren't playing right now.")
            return
        try:
            self._voters.index(user)
            self._gmsg("You already voted, %s, give someone else a chance to "
                       "hate this question" % user)
            return
        except:
            if self._votes < 2:
                self._votes += 1
                self._voters.append(user)
                print(self._voters)
                self._gmsg("%s, you have voted. %s more votes needed to "
                           "skip." % (user, str(3-self._votes)))
            else:
                self._votes = 0
                self._voters = []
                self._next_question(None, None, None)

    def _start(self, args, user, channel):
        '''
        Starts the trivia game.

        TODO: Load scores from last game, if any.
        '''
        if self._lc.running:
            return
        else:
            self._get_new_question()
            self._clue_number = 0
            self._no_plays = 0
            self._lc.start(config.WAIT_INTERVAL)
            self.factory.running = True

    def _stop(self, *args):
        '''
        Stops the game and thanks people for playing,
        then saves the scores.
        '''
        if not self._lc.running:
            return
        else:
            self._lc.stop()
            self._gmsg('Thanks for playing trivia!')
            self._gmsg('Current rankings are:')
            self._standings(None, None, self._game_channel)
            self._gmsg('Scores have been saved, and see you next game!')
            self._save_game()
            self.factory.running = False

    def _save_game(self, *args):
        '''
        Saves the game to the data directory.
        '''
        if not path.exists(config.SAVE_DIR):
            makedirs(config.SAVE_DIR)
        with open(config.SAVE_DIR+'scores.json', 'w') as savefile:
            json.dump(self._scores, savefile)
            print("Scores have been saved.")

    def _load_game(self):
        '''
        Loads the running data from previous games.
        '''
        # ensure initialization
        self._scores = {}
        if not path.exists(config.SAVE_DIR):
            print("Save directory doesn't exist.")
            return
        try:
            with open(config.SAVE_DIR+'scores.json', 'r') as savefile:
                temp_dict = json.load(savefile)
        except:
            print("Save file doesn't exist.")
            return
        for name in temp_dict.keys():
            self._scores[str(name)] = int(temp_dict[name])
        print(self._scores)
        print("Scores loaded.")

    def _set_user_score(self, args, user, channel):
        '''
        Administrative action taken to adjust scores, if needed.
        '''
        try:
            self._scores[args[0]] = int(args[1])
        except:
            self.notice(user, args[0]+" not in scores database.")
            return
        self.notice(user, args[0]+" score set to "+args[1])

    def _restart(self, *args):
        '''
        Restart the bot.
        '''
        self._restarting = True
        self.quit('Restarting eh')

    def _die(self, *args):
        '''
        Terminates execution of the bot.
        '''
        self._quit = True
        self.quit(config.DEFAULT_QUIT)

    def connectionLost(self, reason):
        '''
        Called when connection is lost
        '''
        global reactor
        if self._restarting:
            execl(sys.executable, *([sys.executable]+sys.argv))
        elif self._quit:
            reactor.stop()

    def _score(self, args, user, channel):
        '''
        Tells the user their score.
        '''
        try:
            self.notice(user, "Your current score is: %s" %
                       str(self._scores[user]))
        except:
            self.notice(user, "You aren't in my database.")

    def _next_question(self, args, user, channel):
        '''
        Administratively skips the current question.
        '''
        if not self._lc.running:
            self._gmsg("We are not playing right now.")
            return
        self._gmsg("Question has been skipped. The answer was: %s" %
                   self._answer.answer)
        self._clue_number = 0
        self._lc.stop()
        self._lc.start(config.WAIT_INTERVAL)

    def _standings(self, args, user, channel):
        '''
        Tells the user the complete standings in the game.
        '''
        if channel == self.nickname:
            dst = user
        else:
            if channel != self._game_channel: return
            dst = channel
        score_list = []
        if not user is None:
            self.notice(dst, "The current trivia standings are: ")
        sorted_scores = sorted(self._scores.iteritems(), key=lambda x:x[1], reverse=True)
        for rank, (player, score) in enumerate(sorted_scores, start=1):
            formatted_score = "#%s: %s with %s points" % (rank, player, score)
            score_list.append(formatted_score)
        # Will have to split this at a certain length later
        self.notice(dst, ", ".join([str(player) for player in score_list]))

    def _show_question(self, args, user, channel):
        if not self._lc.running:
            self._gmsg("We are not playing right now.")
            return
        self._gmsg("Current question: %s" % self._question)

    def _give_clue(self, args, user, channel):
        if not self._lc.running:
            self._gmsg("We are not playing right now.")
            return
        # Just stop and start gameplay timer. It will give a new clue
        # and wait another 'WAIT_INTERVAL' until the next clue
        self._lc.stop()
        self._lc.start(config.WAIT_INTERVAL)

    def _get_new_question(self):
        '''
        Selects a new question from the questions directory and
        sets it.
        '''
        damaged_question = True
        while damaged_question:
            # randomly select file
            filename = choice(listdir(self._questions_dir))
            fd = open(config.Q_DIR+filename)
            lines = fd.read().splitlines()
            myline = choice(lines)
            fd.close()
            try:
                self._question, temp_answer = myline.split('`')
            except ValueError:
                print("Broken question:")
                print(myline)
                continue
            self._answer.set_answer(temp_answer.strip())
            damaged_question = False


class ircbotFactory(ClientFactory):
    protocol = triviabot

    def __init__(self, nickname=config.DEFAULT_NICK, realname=config.DEFAULT_NAME):
        self.nickname = nickname
        self.realname = realname
        self.running = False
        self.lineRate = config.LINE_RATE

    def clientConnectionLost(self, connector, reason):
        print("Lost connection (%s)" % (reason,))
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print("Could not connect: %s" % (reason,))
        connector.connect()


if __name__ == "__main__":
    try:
        config.BIND_PORT
    except:
        config.BIND_PORT = randint(40000,43000)
    try:
        config.BIND_ADDR
    except:
        config.BIND_ADDR = '0.0.0.0'
    try:
        config.SERVER_TYPE
    except:
        config.SERVER_TYPE = 'plain'

    BIND = (config.BIND_ADDR, config.BIND_PORT)

    if config.SERVER_TYPE == 'ssl':
        reactor.connectSSL(config.SERVER, config.SERVER_PORT,
                           ircbotFactory(), ssl.ClientContextFactory(),
                           config.TIMEOUT, BIND)
    elif config.SERVER_TYPE == 'plain':
        reactor.connectTCP(config.SERVER, config.SERVER_PORT,
                           ircbotFactory(), config.TIMEOUT, BIND)
    else:
        print('Invalid server_type specified in config.')
        print("Either enter 'ssl', 'plain', or leave commented out.")
        quit()
    reactor.run()
