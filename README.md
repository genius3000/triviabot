This fork is intended to bring in some new features and clean up some questions.
Current modifications include:
 * Got rid of color messages
 * Start/Stop commands are now under user privilege
 * Re-organized the config file and added options for quit msg, real name, usermodes, 
   local bind address, and ssl or plain connection.
 * Answers get unmasked by 25% of their total length each time
 * Increased the points, spruced up the clue messages
 * Fixed the quit command and added a restart

Also merged in more question fixes from [AeroSteveO](https://github.com/AeroSteveO/triviabot)


Original README
--------------
triviabot
=========

A simple IRC trivia bot written in python using twisted.

Features
--------

Simple implementation. Questions are <string>`<string> formatted in plain text files.

Configurable colored text to help differentiate game text from user text.

Event driven implementation: uses very little cycles.

Implementation
--------------

triviabot uses a config.py and comes with an example for you to tweak and use.

Questions exist in files under $BOTDIR/questions.
Each round, a file is selected at random, then a line is selected at random from the file.

The answer is then masked and the question is asked. Periodically, the bot will ask the current question
again and unmask a letter. This happens three times before the answer is revealed.

What the bot doesn't do.
------------------------

  * It doesn't have multiple answers to a question. It shows you the format. Part of the game is to match its formatting.

  * Have error-free questions: the questions come from other bot implementations which themselves had horrible typos.
There needs to be an army of editors to go through the 350+k lines and format them to the standard format for the bot.
The bot was written to catch malformed questions so it wouldn't crash, but if it technically matches <string>`<string>
there's no way for the bot to understand that's not part of the question.

Todo:
-----

Look at the issues. Pull requests welcome.

Released under the GPLv3.
