﻿import os

from google.appengine.ext import db

import datetime
import logging
import json
import webapp2

import clot
from games import Game
from api import hitapi
from players import Player
import lot

class CronPage(webapp2.RequestHandler):
  def get(self):

    for lotInst in lot.LOT.query():
      if not lotInst.hasEnded():
        execute(lot.getLot(lotInst.key))
    
    self.response.write("Cron complete")

def execute(container):
  logging.info("Starting cron for " + container.lot.name + "...")
  checkInProgressGames(container)
  clot.createGames(container)
  clot.setRanks(container)

  #Update the cache. We may not have changed anything, but we update it all of the time anyway. If we wanted to improve this we could set a dirty flag and check it here.
  container.lot.put()
  container.changed()

  logging.info("Cron done")

def checkInProgressGames(container):
  """This is called periodically to look for games that are finished.  If we find a finished game, we record the winner"""

  #Find all games that we think aren't finished
  activeGames = [g for g in container.games if g.winner is None]

  for g in activeGames:
    #call WarLight's GameFeed API so that it can tell us if it's finished or not
    apiret = hitapi('/API/GameFeed?GameID=' + str(g.wlnetGameID), {})
    data = json.loads(apiret)
    state = data.get('state', 'err')
    if state == 'err': raise Exception("GameFeed API failed.  Message = " + data.get('error', apiret))

    if state == 'Finished':
      #It's finished. Record the winner and save it back.
      winner = findWinner(data)
      logging.info('Identified the winner of game ' + str(g.wlnetGameID) + ' is ' + unicode(winner))
      g.winner = winner.key.id()
      g.dateEnded = datetime.datetime.now()
      g.put()
    else:
      #It's still going.
      logging.info('Game ' + str(g.wlnetGameID) + ' is not finished, state=' + state + ', numTurns=' + data['numberOfTurns'])

def findWinner(data):
  """Simple helper function to return the Player who won the game.  This takes json data returned by the GameFeed 
  API.  We just look for a player with the "won" state and then retrieve their Player instance from the database"""
  winnerInviteToken = filter(lambda p: p['state'] == 'Won', data['players'])[0]["id"]
  return Player.query(Player.inviteToken == winnerInviteToken).get()

