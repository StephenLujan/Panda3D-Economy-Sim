# PANDAI PURSUE TUTORIAL
# Author: Srinavin Nair

#for directx window and functions
import math
import sys

from direct.actor.Actor import Actor
import direct.directbase.DirectStart
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.DirectObject import DirectObject
from direct.task import Task
import os
from panda3d.ai import *
from pandac.PandaModules import *
from pandac.PandaModules import Filename
import random

# Globals
speed = 0.75

# Function to put instructions on the screen.
font = loader.loadFont("fonts/cmss12")
# Figure out what directory this program is in.
MYDIR = os.path.abspath(sys.path[0])
MYDIR = Filename.fromOsSpecific(MYDIR).getFullpath()

def addInstructions(pos, msg):
    return OnscreenText(text=msg, style=1, fg=(1, 1, 1, 1), font=font,
                        pos=(-1.3, pos), align=TextNode.ALeft, scale=.05)

def getDistance(A, B):
    return((A.getPos(render) - B.getPos(render)).length())

def getXYDistance(A, B):
    return((A.getPos(render).xy - B.getPos(render).xy).length())

def getSize(object):
    min, max = object.getTightBounds()
    return Point3(max - min).length()

def getRadius(object):
    return getSize(object) * 0.5

class TradeRoute():
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.distance = getDistance(start.productNP, end.resourceNP)
        self.open = False

    def update(self):
        if self.start.canSell() and self.end.canBuy():
            self.open = True
        else:
            self.open = False

class TradeMap():
    def __init__(self):
        self.factories = []
        self.routes = []
        taskMgr.doMethodLater(2, self.update, "tradeMap.update")

    def addFactory(self, factory):
        self.factories.append(factory)

        #check other factories to see if they require our product
        for x in self.factories:
            if self.isTradeRoute(factory, x):
                self.addTradeRoute(factory, x)
        #check other factories to see if they produce our resource
        if factory.resourceType:
            for x in self.factories:
                if self.isTradeRoute(x, factory):
                    self.addTradeRoute(x, factory)

    def addTradeRoute(self, start, end):
        '''Adds a new route to the list of possible trade routes.'''
        t = TradeRoute(start, end)
        t.update()
        self.routes.append(t)

    def isTradeRoute(self, start, end):
        '''Returns true if the start's product is also the end's resource.'''
        if start.productType == end.resourceType:
            return True
        return False

    def update(self, task):
        for x in self.routes:
            x.update()
        return task.again

class Transporter():
    def __init__(self, name, aiworld, tradeMap, position=Vec3(-10, 0, 0)):
        self.name = name
        self.aiworld = aiworld
        self.tradeMap = tradeMap

        self.model = Actor("models/ralph",
                           {"run":"models/ralph-run"})
        self.model.reparentTo(render)
        self.model.setScale(0.5)
        self.model.setPos(position)
        self.model.loop("run")
        self.radius = getRadius(self.model)
        self.rightHand = self.model.exposeJoint(None, 'modelRoot', 'RightHand')

        self.cargo = 0
        self.money = 10
        self.tradeRoute = None
        self.goal = None
        self.initAI()

    def initAI(self):
        self.ai = AICharacter(self.name, self.model, 100, 10, 10)
        self.aiworld.addAiChar(self.ai)
        self.behaviors = self.ai.getAiBehaviors()
        self.behaviors.obstacleAvoidance(0.2)
        self.aiworld.addObstacle(self.model)
        taskMgr.doMethodLater(0.5, self.updateAI, "transporter ai")

    def buy(self, factory):
        '''Buy one product from input factory if possible.'''
        if factory.canSell():
            factory.product -= 1
            factory.updateDisplay()
            self.grab(Cargo(factory.productType))
            return True
        return False


    def sell(self, factory):
        '''Sell one product to input factory if possible.'''
        if factory.canBuy():
            factory.resource += 1
            factory.updateDisplay()
            self.drop()
            return True
        return False

    def grab(self, cargo):
        cargo.carryOn(self.rightHand)
        self.cargo = cargo
    
    def drop(self):
        self.cargo.drop()
        self.cargo = None

    def findTradeRoute(self):
        '''Find the best (shortest) trade route from our current position.
        Currently uses only distance.
        '''
        lowestDistance = 9999999999
        bestRoute = None
        distance = lowestDistance
        for x in self.tradeMap.routes:
            if x.open:
                distance = x.distance + getXYDistance(self.model, x.start.productNP)
                if distance < lowestDistance:
                    bestRoute = x
                    lowestDistance = distance

        return bestRoute

    def findBuyer(self):
        '''We have a product, so we don't need a complete trade route.
        Just find the best (closest) buyer for our product.'''

        if not self.cargo:
            return
        lowestDistance = 9999999999
        bestBuyer = None
        for x in self.tradeMap.factories:
            if x.canBuy():
                if x.resourceType == self.cargo:
                    distance = getXYDistance(self.model, x.resourceNP)
                    if distance < lowestDistance:
                        bestBuyer = x
                        lowestDistance = distance
        return bestBuyer

    def setGoal(self, goal):
        self.goal = goal
        print self.name,"'s goal: ",self.goal

    def updateAI(self, task):

        # If ai has no current goal, try to find one.
        if (self.goal == None):
            if (self.tradeRoute == None):
                self.tradeRoute = self.findTradeRoute()
            if (self.tradeRoute == None):
                return Task.again
            if (self.cargo):
                self.setGoal(self.tradeRoute.end)
            else:
                self.setGoal(self.tradeRoute.start)

        # If we still don't have a goal just try again later.
        if (self.goal == None):
            return Task.again

        if (self.cargo):
            # We have the product. Go to resource point for trade route ending.
            dockingDistance = self.radius + self.goal.getResourceRadius()
            if (getXYDistance(self.model, self.goal.resourceNP) > dockingDistance):
                self.behaviors.seek(self.goal.resourceNP, 0.5)
            else:
                self.tradeRoute = None
                if self.sell(self.goal):
                    self.setGoal(None)
                else:
                    self.setGoal(self.findBuyer())
        else:
            # We have no product. Go to product point of trade route start.
            dockingDistance = self.radius + self.goal.getProductRadius()
            if (getXYDistance(self.model, self.goal.productNP) > dockingDistance):
                self.behaviors.seek(self.goal.productNP, 0.5)
            else:
                if not self.buy(self.goal):
                    self.tradeRoute = None
                self.setGoal(None)

        return Task.again



class Factory():
    def __init__(self, name, aiworld, position=Vec3(0, 0, 0), resourceType=0, productType=1):
        self.name = name
        self.aiworld = aiworld
        self.resourceType = resourceType
        self.productType = productType

        self.model = loader.loadModel("models/box")
        self.model.setScale(0.2)
        self.model.setPos(position)
        self.model.reparentTo(render)

        self.productNP = NodePath(PandaNode("product"))
        self.productNP.reparentTo(self.model)
        self.productNP.setPos(5, 0, 15)
        self.productNP.setTransparency(TransparencyAttrib.MAlpha)
        self.productModel = Cargo(productType)
        self.productModel.model.reparentTo(self.productNP)

        if resourceType:
            self.resourceNP = NodePath(PandaNode("resource"))
            self.resourceNP.reparentTo(self.model)
            self.resourceNP.setPos(-5, 0, 15)
            self.resourceNP.setTransparency(TransparencyAttrib.MAlpha)
            self.resourceModel = Cargo(resourceType)
            self.resourceModel.model.reparentTo(self.resourceNP)

        self.product = 0
        self.resource = 0
        self.money = 10
        self.initAI()

        taskMgr.doMethodLater(5, self.makeProduct, "makeProduct")
        self.updateDisplay()

    def initAI(self):
        self.aiworld.addObstacle(self.model)

    def makeProduct(self, task):

        if self.resourceType:
            if self.resource > 0:
                self.resource -= 1
            else:
                return Task.again

        self.product += 1
        self.updateDisplay()
        return Task.again

    def updateDisplay(self):
        if self.product > 0:
            self.productNP.setScale(math.sqrt(self.product))
            self.productNP.setAlphaScale(1)
        else:
            self.productNP.setAlphaScale(0.3)

        if not self.resourceType:
            return

        if self.resource > 0:
            self.resourceNP.setScale(math.sqrt(self.resource))
            self.resourceNP.setAlphaScale(1)
        else:
            self.resourceNP.setAlphaScale(0.3)

    def canBuy(self):
        if not self.resourceType:
            return False
        return True

    def canSell(self):
        if self.product > 0:
            return True
        return False

    def getResourceRadius(self):
        return getRadius(self.resourceModel.model) * self.model.getScale().x * self.resourceNP.getScale().x

    def getProductRadius(self):
        return getRadius(self.productModel.model) * self.model.getScale().x * self.productNP.getScale().x

class Cargo():
    def __init__(self, type=1):
        self.model = loader.loadModel("models/teapot")
        self.type = type
        
        if type == 1:
            c = (1, 0, 0, 1)
        elif type == 2:
            c = (0, 1, 0, 1)
        elif type == 3:
            c = (0, 0, 1, 1)
        self.model.setColor(c)
    def carryOn(self, carrier):
        self.model.setPos(0, -1.3, 0)
        self.model.setHpr(-90, 180, 0)
        self.model.setScale(0.5)
        self.model.reparentTo(carrier)

    def drop(self):
        self.model.removeNode()



class World(DirectObject):

    def __init__(self):
        #base.disableMouse()
        base.cam.setPosHpr(0, 0, 55, 0, -90, 0)
        self.AIworld = AIWorld(render)
        self.tradeMap = TradeMap()

        self.loadModels()
        self.setMovement()
        self.setAI()

    def loadModels(self):
        # transporter
        self.trans = Transporter('Mr. Red', self.AIworld, self.tradeMap, Vec3(-10, 0, 0))
        self.trans.model.setColor(1,0,0)

        self.trans = Transporter('Mr. Green', self.AIworld, self.tradeMap, Vec3(3, -3, 0))
        self.trans.model.setColor(0,1,0)

        self.trans = Transporter('Mr. Blue', self.AIworld, self.tradeMap, Vec3(10, 3, 0))
        self.trans.model.setColor(0,0,1)

        #test
        #self.trans.grab(Cargo())

        # Target
        self.target = loader.loadModel("models/arrow")
        self.target.setColor(1, 0, 0)
        self.target.setPos(5, 0, 0)
        self.target.setScale(1)
        self.target.reparentTo(render)

        # factories
        self.tradeMap.addFactory(Factory('fac1', self.AIworld, Vec3(0, -5, 0)))
        self.tradeMap.addFactory(Factory('fac2', self.AIworld, Vec3(7, 5, 0), 1, 2))
        self.tradeMap.addFactory(Factory('fac3', self.AIworld, Vec3(8, -7, 0), 1, 2))
        self.tradeMap.addFactory(Factory('fac4', self.AIworld, Vec3(-3, 8, 0), 2, 3))
        self.tradeMap.addFactory(Factory('fac5', self.AIworld, Vec3(-7, -6, 0)))
        
      
    def setAI(self):
        #AI World update        
        taskMgr.add(self.AIUpdate, "AIUpdate")
        
    #to update the AIWorld    
    def AIUpdate(self, task):
        self.AIworld.update()            
        return Task.cont

    #All the movement functions for the Target
    def setMovement(self):
        self.keyMap = {"left":0, "right":0, "up":0, "down":0}
        self.accept("arrow_left", self.setKey, ["left", 1])
        self.accept("arrow_right", self.setKey, ["right", 1])
        self.accept("arrow_up", self.setKey, ["up", 1])
        self.accept("arrow_down", self.setKey, ["down", 1])
        self.accept("arrow_left-up", self.setKey, ["left", 0])
        self.accept("arrow_right-up", self.setKey, ["right", 0])
        self.accept("arrow_up-up", self.setKey, ["up", 0])
        self.accept("arrow_down-up", self.setKey, ["down", 0])
        #movement task
        taskMgr.add(self.Mover, "Mover")
        
        addInstructions(0.9, "Use the Arrow keys to move the Red Target")

    def setKey(self, key, value):
        self.keyMap[key] = value
            
    def Mover(self, task):
        startPos = self.target.getPos()
        if (self.keyMap["left"] != 0):
            self.target.setPos(startPos + Point3(-speed, 0, 0))
        if (self.keyMap["right"] != 0):
            self.target.setPos(startPos + Point3(speed, 0, 0))
        if (self.keyMap["up"] != 0):
            self.target.setPos(startPos + Point3(0, speed, 0))
        if (self.keyMap["down"] != 0):
            self.target.setPos(startPos + Point3(0, -speed, 0))
                        
        return Task.cont
 
w = World()
run()
