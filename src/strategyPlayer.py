from alpaga import *
from strategy import *
from pycudd import *
import pycudd
import sys
import commands
import cmd
import readline 
import random 

class exit_cmd(cmd.Cmd, object): 

    def can_exit(self): 
        return True 

    def onecmd(self, line):
        r = super (exit_cmd, self).onecmd(line)
        if r and (self.can_exit() or 
           raw_input('exit anyway ? (yes/no):')=='yes'): 
             return True
        return False 

    def do_exit(self, s):
        print "\nBye !"
        quit()
        return True

    def help_exit(self): 
        print "Exit the interpreter."
        print "You can also use the Ctrl-D shortcut." 

    do_EOF = do_exit 
    help_EOF= help_exit



class StrategyPlayer(exit_cmd, object):
    #class for cell strategies
    def __init__(self,game,strategy):
        cmd.Cmd.__init__(self)
        self.dict={}
        self.game=game
        self.strategy=strategy
        self.knowledge=game.initBDD
#        self.completekey=None
#        self.cmdqueue=None
        self.prompt=">>"
        self.intro="GSolv interactive mode \n ----------------------"
    def preloop(self): 
        print 'Available commands : go , exit, reinit, help, summary' 
            
    def do_go(self,s): 
        print "------------------------------------------"
        self.printKnowledge()
        move= self.strategy.getMoveForCell(self.knowledge)
        print "The Strategy plays : " , move
        self.knowledge = self.game.computeSuccessorsBDD(self.game.BDDLabelDict[move] , self.knowledge)
        self.printKnowledge()
        self.printObservations()
        choice=-1
        while (choice <=0 or choice>len(self.obsList)):
            s= raw_input('Pick a number (keep blank for random) : ')
            if s=="":
                choice = random.choice(range(len(self.obsList)))+1  
            else :          
                try : 
                    choice = int(s)
                except ValueError:
                    choice=-1
        self.knowledge=self.knowledge & self.obsList[choice-1]
        self.printKnowledge()
            
    def default(self, s):
        self.do_go(s)
        
    def printObservations(self):
        count=1
        self.obsList=[]
        print "The possible next observations are : "
        for obs in self.game.obsBDDList:
            if obs & self.knowledge != ~self.game.manager.ReadOne():
                print count , " : " ,
                self.game.printSet(obs)
                self.obsList.append(obs)
                count +=1
    def do_summary(self,s):
        print "Winning Cells :" 
        self.game.printAntichain(self.game.W)
        print "Strategy :"
        self.strategy.display()
        self.printKnowledge()  
    
    def help_summary(self):
        print "Print a summary of the current situation :"
        print "   -Winning cells"
        print "   -Strategy"
        print "   -Current knowledge"
         
    def printKnowledge(self):
       print "Current Knowledge : "
       self.game.printSet(self.knowledge)
                
    def do_reinit(self,s):
        self.knowledge=self.game.initBDD
    
    def help_go(self):
        print "Make the game progress  from the current knowledge,"
        print "allowing you to pick interactively the observation"
        print "(After typing one time go, it becomes the default :"
        print "it suffices to press enter to do it again)"
    
    def help_reinit(self):
        print "Reinitialize the current knowledge to the set of initial states"
    
    def help_help(self):
        print "help commandName gives you information on the GSolv interactive"
        print "command of name commandName"

            


        
