from alpaga import *
from pycudd import *
import pycudd
import sys
import commands
from heapq import heappush, heappop

class triple(object):
    """
    A utility class to allow to easily sort the moves of a strategy
    using a heapsort
    """
    def __init__(self,cell,move,rank):
        self.cell=cell
        self.move=move
        self.rank=rank
    
    def __le__(self,other):
        return self.rank<= other.rank
    
    def __repr__(self):
        return str(self.move)+" , "+str(self.rank)
    
class Strategy(object):
    #class for cell strategies
    def __init__(self,game,rank=0):
        self.dict={}
        self.game=game
        self.rank=rank

    def setCellMove(self,cellBDD,move):
        if not cellBDD in self.dict:
            self.dict[cellBDD]=(move,self.rank)
    
    def setCellMoveRank(self,cellBDD,move,rank):
        if not cellBDD in self.dict:
            self.dict[cellBDD]=(move,rank)
        elif self.dict[cellBDD][1]>rank:
            self.dict[cellBDD]=(move,rank)
            
    def getCellMove(self,cellBDD):
        return self.dict[cellBDD][0]
    def getCellRank(self,cellBDD):
        return self.dict[cellBDD][1]
       
    def getCellMoveRank(self,cellBDD):
        return self.dict[cellBDD]
    
    def union(self,strategy2):
        res=Strategy(self.game)
        for elem in self.dict:
            res.setCellMoveRank(elem,self.getCellMove(elem),self.getCellRank(elem))
        for elem in strategy2.dict:
            res.setCellMoveRank(elem,strategy2.getCellMove(elem),strategy2.getCellRank(elem))
        res.rank=max(self.rank,strategy2.rank)
        return res
  
    def addMovesWithCurrentRank(self,strategy2):
        for elem in strategy2.dict:
            self.setCellMoveRank(elem,strategy2.getCellMove(elem),self.rank)
    
    def increaseRank(self):
        self.rank+=1
    
    def getMaxRank(self):
        return self.rank
    
    def increaseAllMovesRank(self,increase):
        self.rank+=increase
        for cell in self.dict:
            move,rank =self.dict[cell]
            self.dict[cell]=move,rank+increase
    
    def display(self, collapsed=True):
        heap=[]
        for cell in self.dict : 
            heappush(heap,triple(cell,self.getCellMove(cell),self.getCellRank(cell)))
        lastRank=0
        printedRank=0
        while heap:
             tr = heappop(heap)
             if not collapsed : 
                 print "("+ tr.move + ", "+ str(tr.rank)+ ") : ", 
             else :
                 if tr.rank!= lastRank :
                     lastRank = tr.rank
                     printedRank+=1 
                 print "("+ tr.move + ", "+ str(printedRank)+ ") : ",
             self.game.printSet(tr.cell)

    def simplify(self):
        #### rule 1 
        oldDict={}
        while oldDict!=self.dict:
            
            oldDict=self.dict
            tempDict={}
            for cell1 in self.dict:
                greaterFound=False
                for cell2 in self.dict:
                    if cell1!= cell2 and self.game.includedIn(cell1,cell2) :#needs further investigation
                       if self.getCellRank(cell1) >= self.getCellRank(cell2):
                           greaterFound=True
                           break;
                if not greaterFound : 
                    tempDict[cell1]= self.getCellMoveRank(cell1)

            self.dict=tempDict
            #### rule 2 
    
            tempDict={}
            for cell1 in self.dict: 
                toKeep=True
                for cell2 in self.dict : 
                    if cell1!= cell2 and self.getCellMove(cell1)== self.getCellMove(cell2) and self.game.includedIn(cell1,cell2):

                        forall=True
                        for cell3 in self.dict : 
                            if cell1!=cell2 and cell2!=cell3 and self.getCellMove(cell1)!=self.getCellMove(cell3) and self.getCellRank(cell3) < self.getCellRank(cell2) and self.getCellRank(cell3) > self.getCellRank(cell1) and cell3 & cell1 != ~self.game.manager.ReadOne():
                                forall=False

                                break;
                        toKeep=not forall
                if toKeep:
                    tempDict[cell1]= self.getCellMoveRank(cell1)
    
            self.dict=tempDict
    
    def getMoveForCell(self,cell):
        min = ("",self.rank+1)
        for cell2 in self.dict: 
            if self.game.includedIn(cell,cell2):
                move,rank = self.getCellMoveRank(cell2)
                if rank< min[1]:
                    min=(move,rank)
        return min[0]
    
    
        
