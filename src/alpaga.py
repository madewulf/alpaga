#! /usr/bin/env python
from pycudd import *
import pycudd
from math import log, ceil
import sys
import commands
from parser import *
from strategy import *
from optparse import OptionParser
from time import time
from strategyPlayer import *
class Game(object):
    """
    The main class of alpaga. The following fields are initialized by the parser : 
    manager : the PyCudd manager
    BDDLocDict : a dictionary from state id string to state BDDs
    locsCubeBDD : the cube of the state variables (see CUDD doc for the definition of cubes)
    locCubeArray: the cube of the state variables (see CUDD doc). Arrays are used in quantification
    locsPrimedCubeBDD : same as locsCubeBDD but for the primed variables representing the destination states in the transition relation
    locPrimedCubeArray : same as locCubeArray but for the primed variables representing the destination states in the transition relation
    BDDLabelDict :  a dictionary from label id string to label BDDs
    labelsCubeBDD : the cube for labels
    labelCubeArray : the array for labels variables
    maxid : the maximum variable index defined after the parsing (beware, other variables could be added by addLinearEncoding
    nloc : the number of states
    locMask : the mask for states (see DOC.txt)
    transBDD : the BDD of the transition relation
    initBDD : the BDD of the set of initial states
    targetBDD: the BDD of the set of target states
    safeBDD : the BDD of the set of safe states
    obsBDDList : the list of BDDs, each one  representing an observation
    locNLogVar : the number of variables used to represent states
    obsPrioDict : a dictionary from obs BDD to their priority
    prioBDDDict : a dictionary from priority integer to set of states whith those priorities
    maxPriority : the maximum priority used in the game (performances tend to depend a lot on this value)
    """


    def __init__(self):
        self.locNLogVar=0
        self.BDDLocDict=None
        self.reach=None
        self.safe=None
        self.parser=None

    def createAntichainFromLinearEncoding(self,cpreBDD):
        """
        Creates an antichains as a (python) set of BDDs from an
        antichain encoded in a BDD in linear encoding
        """
        antichain=set()
        strat=Strategy(self)
        cpt=0
        while cpreBDD:
            m = cpreBDD.PickOneMinterm(self.linearCubeArray, self.nloc)
            temp= m & cpreBDD
            for label in self.BDDLabelDict:
                if (self.BDDLabelDict[label] & temp != ~self.manager.ReadOne()):
                    lab=label
                    break
            cpreBDD &= ~m 
            s=~self.manager.ReadOne()
            for loc in self.BDDLinearIdDict:
                if (m & self.BDDLinearIdDict[loc]!= ~self.manager.ReadOne()):
                    s = s |self.BDDLocDict[loc]
            if s!=~self.manager.ReadOne():
                antichain.add(s) 
                strat.setCellMove(s,lab)
            cpt=cpt+1
        return antichain, strat
    
    def includedIn(self, set1,set2):
        """
        Returns True iff set1 is included in set 2
        """
        if imp(set1,set2)== self.manager.ReadOne():
            return True
        else :
            return False
    
    def includedInAntichain(self,set1,antichain):
        """
        Returns True iff set 1 is included in a set of antichain
        """
        for set2 in antichain:
            if self.includedIn(set1,set2):
                return True
        return False
    
    def sqsubseteq(self,antichain1,antichain2):
        """
        Returns True iff every set of antichain1 is included in a set
        of antichain2
        """
        for set1 in antichain1:
            if not self.includedInAntichain(set1,antichain2):
                return False
        return True
    
    def antichainInsert(self, antichain, setToInsert):
        """
        Insert setToInsert into antichain
        """
        res=set([])
        included=False
        for s in antichain:
            if self.includedIn( setToInsert,s):
                res=antichain
                included=True
                break
            if not ( self.includedIn( s, setToInsert)):
                res.add(s)
        if not included :
            res.add(setToInsert)
        return res
    
    def antichainUnion(self, antichain1,antichain2):
        """
        Computes the least greater bound of antichain1 and antichain2
        """
        res=antichain2
        for set in antichain1:
            res=self.antichainInsert(res,set)
        return res        
        
        
    def antichainIntersection(self, antichain1, antichain2):
        """
        Computes the greatest lower bound of antichain1 and antichain2
        """
        res=set([])
        for set1 in antichain1:
            for set2 in antichain2 : 
                temp =set1 & set2
                if temp!=~self.manager.ReadOne():
                    res=self.antichainInsert(res,set1 & set2)
        return res
    
    def computeReachable(self):
        """
        Compute the set of reachable states of the game. 
        Not used anywhere right now
        """
        brol=set()
        if self.reach==None:
             reachable= self.initBDD
             previous= ~self.manager.ReadOne()
             niter=0
             while (reachable != previous):
                niter+=1
                previous= reachable
                new = self.post(reachable)
                reachable=reachable | new
             self.reach=reachable
        return self.reach
    
    def post(self,cell):
        """
        Computes the set of successors (on any label) of the set of state cell
        """
        res= cell & self.transBDD
        res=res.ExistAbstract(self.labelsCubeBDD)
        res=res.ExistAbstract(self.locsCubeBDD)
        res=res.SwapVariables(self.locCubeArray,self.locPrimedCubeArray,self.locNLogVar)
        return res
    
    def post_sigma(self,cell,sigma):
        """
        Computes the set of successors on label sigma of the set of state cell
        """
        res= cell & self.transBDD & self.BDDLabelDict[sigma]
        res=res.ExistAbstract(self.labelsCubeBDD)
        res=res.ExistAbstract(self.locsCubeBDD)
        res=res.SwapVariables(self.locCubeArray,self.locPrimedCubeArray,self.locNLogVar)
        return res
    
    def computeReach(self,targetAntichain=None):
        """
        Computes the set of winning states for the objective Reach(targetAntichain)
        If targetAntichain is not specified, use the target of the game
        """
        X=self.getMinAntichain()
        oldX=self.getMaxAntichain()
        if targetAntichain==None:
            targetAntichain=set([self.targetBDD])
    
        while (X!=oldX):
            oldX=X
            cp, a=self.cpre(X)
            X=self.antichainUnion(cp,targetAntichain)
        return X
        
    def computeReachStrat(self,targetAntichain=None):
        """
        Computes the set of winning states and a winning strategy for
        the objective Reach(targetAntichain) If targetAntichain is not
        specified, use the target of the game
        """

        strat=Strategy(self)
        X=self.getMinAntichain()
        oldX=self.getMaxAntichain()
        if targetAntichain==None:
            targetAntichain=set([self.targetBDD])
        while (X!=oldX):
            oldX=X
            cp, tempStrat=self.cpre(X)
            strat.addMovesWithCurrentRank(tempStrat)
            strat.increaseRank()
            X=self.antichainUnion(cp,targetAntichain)
        return X ,strat    

    def computeReachAndSafe(self,T,F):
        """
        Computes the set of winning states for the objective
        ReachAndSafe(T,F) (see references/concurO8.pdf)
        """
        X=set()
        oldX=set([self.locMask])
        while(X!=oldX):
            oldX=X
            CP, a=self.cpre(X)
            uni=self.antichainUnion([self.targetBDD],CP)
            X=self.antichainIntersection(uni,[self.safeBDD])
        return X
       
    def computeReachAndSafeStrat(self,T,F):
        """
        Computes the set of winning states and a winning strategy for
        the objective ReachAndSafe(T,F) (see references/concurO8.pdf)
        """
        strat=Strategy(self)
        X=set()
        oldX=set([self.locMask])
        while(X!=oldX):
            oldX=X
            CP, tempStrat=self.cpre(X)
            strat.addMovesWithCurrentRank(tempStrat)
            strat.increaseRank()
            uni=self.antichainUnion(T,CP)
            X=self.antichainIntersection(uni,F)
        return X, strat   

    def computeReachOrSafe(self,T,F):
        """
        Computes the set of winning states for the objective
        ReachOrSafe(T,F) (see references/concurO8.pdf)
        """
        TStar=self.computeReach(T)
        
        X=set([self.locMask])
        oldX=set()
        while(X!=oldX):
            oldX=X
            CP, a=self.cpre(X)
            inter=self.antichainIntersection([self.safeBDD],CP)
            X=self.antichainUnion(inter,TStar)
        return X
    
    def computeReachOrSafeStrat(self,T,F):
        """
        Computes the set of winning states and a strategy for the
        objective ReachOrSafe(T,F) (see references/concurO8.pdf)
        """

        TStar,strat=self.computeReachStrat(T)
        
        X=set([self.locMask])
        oldX=set()
        while(X!=oldX):
            oldX=X
            CP, a =self.cpre(X)
            inter=self.antichainIntersection(F,CP)
            X=self.antichainUnion(inter,TStar)
        stratBis= self.computeSafetyStratFromAntichain(X)
        
        return X, stratBis.union(strat)  



    def computeSafetyStratFromAntichain(self,antichain):
        """
        Computes a winning strategy for a safety objective given the
        antichain of winning sets for this objective
        """
        strat=Strategy(self)
        for cell in antichain: 
            for sigma in self.BDDLabelDict:
                ok=True
                for obsBDD in self.obsBDDList:
                    post=self.post_sigma(cell,sigma)
                    inter=post & obsBDD
                    if not(self.includedInAntichain(inter,antichain)):
                        ok=False
                        break;
                if ok:
                    strat.setCellMove(cell,sigma)
                    break;
        return strat
                    
    def solve(self,T, F, pModifier=0):  
        """ 
        The solve algorithm from CONCUR08 adapted to antichains (see
        references/concur08.pdf) and DOC.txt for more information
        """
        self.T=T
        self.F=F             
        W=self.computeParityObjective(pModifier)
        WStar,alphaStar= self.computeReachAndSafeStrat(self.T,W)
        inter= self.antichainIntersection([self.getCellFromPriority(0-pModifier)],W)
        union=self.antichainUnion(inter, WStar)
        W_0, alpha_0 = self.computeReachAndSafeStrat(union,W)
        junk, alpha_prime_0= self.computeSafeStrat(inter) 
        alpha_prime_0.increaseAllMovesRank(max(alpha_0.getMaxRank()+1,alphaStar.getMaxRank()+1))
        bar_alpha_i= alpha_0.union(alpha_prime_0.union(alphaStar))
        i=0
        W_i=W_0
        oldW_i=self.getMaxAntichain()
        while (W_i!=oldW_i):
            oldW_i=W_i
            union012=~self.manager.ReadOne()
            for kk in range(0,3-pModifier):
                if kk in self.prioBDDDict:
                    c_p_kk=self.getCellFromPriority(kk)
                    union012=c_p_kk | union012      
            union012 = set([union012])      
            if self.sqsubseteq(W,union012):
                W_i,newAlpha_i = self.computeReachOrSafeStrat(W_i,[self.getCellFromPriority(2-pModifier)]) 
            else:
                difference=self.getMinAntichain()
                for j in range(2,len(self.prioBDDDict)+pModifier+1):
                    if (j-pModifier) in self.prioBDDDict:
                        difference= self.antichainUnion(set([self.getCellFromPriority(j-pModifier)]),difference)
                W_i,newAlpha_i=self.solve(W_i,difference,pModifier-2)
            newAlpha_i.increaseAllMovesRank(bar_alpha_i.getMaxRank()+1)
            bar_alpha_i= bar_alpha_i.union(newAlpha_i)
        return W_i , bar_alpha_i
        
    def getMaxAntichain(self):
        """
        Returns the antichains containing on set only : the whole set
        of states
        """
        return set([self.locMask])
    
    def getCellFromPriority(self,prio):
        """
        Returns the set of states of priority prio
        """
        if prio in self.prioBDDDict:
            return self.prioBDDDict[prio]
        else:
            return ~self.manager.ReadOne()
    
    def getMinAntichain(self):
        """
        Returns the minimal antichain : the empty set
        """
        return set()
    
    def computeBuchiObjective(self):
        """
        Specific function for solving buechi objectives.
        Currently not used anywhere
        """
        x0=self.getMaxAntichain()
        oldx0=self.getMinAntichain()
        while(x0!=oldx0):
            self.printAntichain(x0)
            oldx0=x0
            x1=self.getMinAntichain()
            oldx1=self.getMaxAntichain()
            while(x1!=oldx1):
                self.printAntichain(x1)
                oldx1=x1

                cp1, a=self.cpre(x1)
                self.printAntichain(cp1)
                p1=[self.getCellFromPriority(1)]
                self.printAntichain(p1)
                cp0, a=self.cpre(x0)
                p0=[self.getCellFromPriority(0)]
                temp1=self.antichainIntersection(p1,cp1)
                temp0=self.antichainIntersection(p0,cp0)  
                x1=self.antichainUnion(temp1,temp0)
            x0=x1    
        
        return x0

    def evaluateFPointInnerFormula(self,antichainList,pModifier=0):
        """
        Evaluates the inner formula of the fixpoint with multiple imbrication describing the 
        set of winning sets for a parity condition (see DOC.txt for more info)
        """
        res=set([])
        prio=0
        
        reachT=self.computeReach(self.T)
        for antichain in antichainList:

                cp, a=self.cpre(antichain)
                p=[self.getCellFromPriority(prio-pModifier)]
                intersection=self.antichainIntersection(p,cp)
                intersection=self.antichainIntersection(intersection,self.F)
                res=self.antichainUnion(res,intersection)
                prio=prio+1
        res=self.antichainUnion(res,reachT)
        return res
    
    
    def computeParityLFPRec(self,antichainList,index,pModifier=0):
        """
        Computes a least fixpoint in the formula of the parity
        condition (see DOC.txt)
        """
        antichainList[index]=self.getMinAntichain()
        oldX=self.getMaxAntichain()
        while(antichainList[index]!=oldX):
            oldX=antichainList[index]
            if len(antichainList)==index+1:
                antichainList[index]=self.evaluateFPointInnerFormula(antichainList,pModifier)
            else:
                antichainList[index]=self.computeParityGFPRec(antichainList,index+1,pModifier)
        return antichainList[index]
    
    def computeParityGFPRec(self,antichainList,index,pModifier=0):
        """
        Computes a greatest fixpoint in the formula of the parity
        condition (see DOC.txt)
        """
        antichainList[index]=self.getMaxAntichain()
        oldX=self.getMinAntichain()
        while(antichainList[index]!=oldX):
            oldX=antichainList[index]
            if len(antichainList)==index+1:
                antichainList[index]=self.evaluateFPointInnerFormula(antichainList,pModifier)
            else:
                antichainList[index]=self.computeParityLFPRec(antichainList,index+1,pModifier)
        return antichainList[index]

    def computeParityObjective(self,pModifier=0):    
        """
        Computes the antichain of winning sets for the parity objective (+safety and reachability), that is : 
        Reach(TARGET) or (parity(p) and safe(SAFE)) where p is a function attributing parity to observations 
        (which corresponds to obsPrioDict in the code).
        """
        antichainList=[]
        for prio in range(self.maxPriority+1+pModifier):
            antichainList.append([])
        return self.computeParityGFPRec(antichainList,0,pModifier)
                         
    def cpreSemiSymbolic(self,antichain):
        """
        A straightforward implemenation of the cpre operator, that
        just enumerates labels, observations and sets of antichain,
        computing needed union and intersection along the way (where
        the other methods of the function cpre avoids to explicitely
        computing the intersection)
        """
        cpre=[]
        for sigma in self.BDDLabelDict:
            intersection=[self.manager.ReadOne()]
            for obs in self.obsBDDList:
                union=[]
                for set in antichain :
                    temp= ~obs & self.locMask
                    temp= set | temp
                    temp= ~temp & self.locMask
                    temp= temp.SwapVariables(self.locCubeArray,self.locPrimedCubeArray,self.locNLogVar)
                    temp= temp & self.transBDD & self.BDDLabelDict[sigma]
                    temp=temp.ExistAbstract(self.labelsCubeBDD)
                    temp=temp.ExistAbstract(self.locsPrimedCubeBDD)
                    temp=~temp & self.locMask
                    union= self.antichainUnion([temp] , union)
                intersection=self.antichainIntersection(union,intersection)
            cpre=self.antichainUnion(cpre,intersection)
        return cpre
    
    def cpreStratSemiSymbolic(self,antichain):
        """
        A straightforward implemenation of the cpre operator, that
        just enumerates labels, observations and sets of antichain,
        computing needed union and intersection along the way (where
        the other methods of the function cpre avoids to explicitely
        computing the intersection)

        This function outputs the cpre + a strategy enforcing the game
        to stay in antichain from the sets in the cpre
        """

        if not self.options.enumerative:
            print "ERROR : the semi symbolic cpre should not be used !!!!"
        cpre=[]
        tempStrat=Strategy(self)
        for sigma in self.BDDLabelDict:
            intersection=[self.manager.ReadOne()]
            for obs in self.obsBDDList:
                union=[]
                for set in antichain :
                    temp= ~obs & self.locMask
                    temp= set | temp
                    temp= ~temp & self.locMask
                    temp= temp.SwapVariables(self.locCubeArray,self.locPrimedCubeArray,self.locNLogVar)
                    temp= temp & self.transBDD & self.BDDLabelDict[sigma]
                    temp=temp.ExistAbstract(self.labelsCubeBDD)
                    temp=temp.ExistAbstract(self.locsPrimedCubeBDD)
                    temp=~temp & self.locMask
                    union= self.antichainUnion([temp] , union)
                intersection=self.antichainIntersection(union,intersection)
            for cell in intersection:#Here, we could write for cel in intersection and cpre, to keep only the moves that really appears in the strategy ???
                tempStrat.setCellMove(cell,sigma)
            cpre=self.antichainUnion(cpre,intersection)
        strat=Strategy(self)
        for cell in cpre:
            strat.setCellMove(cell,tempStrat.getCellMove(cell))
        return cpre, strat
    
    
    def computeObsSelector(self):
        """
        Computes a BDD that serves as a selector in the computation of
        the cpre: for every observations, one binary variables is
        added and the result of this function is a BDD for which if
        the added variable of relative index i is True, then the
        formula expressing the corresponding observation is true too.
        """
        self.obsIdList=[]
        for i in range(len(self.obsBDDList)):
            self.obsIdList.append("obs"+str(i))
        self.BDDObsIdDict, self.obsIdCubeBDD, self.maxid, self.obsIdCubeArray = self.parser.buildBDDFramework( self.obsIdList, self.manager, self.maxid)
  
        
        self.obsSelector=self.manager.ReadOne()
        i=0
        self.obsMask=~self.manager.ReadOne()
        for obsId in self.obsIdList:
            self.obsSelector = self.obsSelector & (imp(self.BDDObsIdDict[obsId], self.obsBDDList[i]))
            self.obsMask= self.obsMask | self.BDDObsIdDict[obsId]
            i+=1
        return self.obsSelector
    
    def computeCPREBDDLAB(self,antichain,sigmaBDD):
        """
        Computes the cpre in linear encoding of antichain for label Sigma
        """
        cp_sigma= ~self.manager.ReadOne()
        for s in antichain:
            conjunction = self.manager.ReadOne()
            for loc in self.BDDLocDict:
                t_sigma_li=self.computeSuccessorsBDD(sigmaBDD,self.BDDLocDict[loc])
                temp = imp(t_sigma_li & self.obsSelector,s)
                temp2= temp.UnivAbstract(self.locsCubeBDD)
                temp3=imp(self.BDDLinearIdDict[loc],temp2)
                conjunction=conjunction & temp3
            conjunction = conjunction | ~self.obsMask
            cp_sigma=cp_sigma | conjunction
        cp_sigma=cp_sigma.UnivAbstract(self.obsIdCubeBDD)
        cp_sigma= cp_sigma & sigmaBDD
        return cp_sigma

    def computeCPREBDD(self,antichain):
        """
        Computes the cpre in linear encoding of antichain
        """
        cpre=~self.manager.ReadOne()
        for sigma in self.BDDLabelDict:
            cpre=cpre | self.computeCPREBDDLAB(antichain,self.BDDLabelDict[sigma])
        return cpre
    
    def cpre(self,antichain):
        """
        Compute the antichain of controllable predecessors sets of
        antichain (enumeratively or not, depending on self.options.enumerative
        """
        if self.options.enumerative :
            return self.cpreStratSemiSymbolic(antichain)
        cp=self.computeCPREBDD(antichain)
        
        cpPrimed=cp.SwapVariables(self.linearCubeArray,self.linearPrimedCubeArray,self.nloc)
        
        temp =cpPrimed & self.strictInclusion
        temp2 = ~temp.ExistAbstract(self.linearPrimedCubeBDD)
        cpreBDD= cp & temp2

        return self.createAntichainFromLinearEncoding(cpreBDD)
        
    def addLinearLocEncoding(self):
        """
        a function called to initialize the data
        structures used when computing the cpre that is not enumerative (see
        the introduction paper to alaska for more insight about this). If
        the enumerative cpre is used, this function has not to be called.
        """
        self.computeObsSelector()
        self.linearCubeArray= DdArray(self.nloc)
        self.linearPrimedCubeArray= DdArray(self.nloc)
        index=0
        self.BDDLinearIdDict={}
        self.BDDLinearPrimedIdDict={}
        conjunction=self.manager.ReadOne()
        disjunction=~self.manager.ReadOne()
        self.linearCubeBDD=self.manager.ReadOne()
        self.linearPrimedCubeBDD=self.manager.ReadOne()
        for loc in self.BDDLocDict:
            self.linearCubeArray[index]=self.manager.IthVar(self.maxid)
            self.BDDLinearIdDict[loc]=self.linearCubeArray[index]
            self.linearCubeBDD=self.linearCubeBDD & self.linearCubeArray[index]
            self.maxid=self.maxid+1
            
            self.linearPrimedCubeArray[index]=self.manager.IthVar(self.maxid)
            self.BDDLinearPrimedIdDict[loc]=self.linearPrimedCubeArray[index]
            self.linearPrimedCubeBDD=self.linearPrimedCubeBDD & self.linearPrimedCubeArray[index]
            self.maxid=self.maxid+1
            conjunction = conjunction & imp(self.BDDLinearIdDict[loc],self.BDDLinearPrimedIdDict[loc])
            disjunction = disjunction | ~iff(self.BDDLinearIdDict[loc],self.BDDLinearPrimedIdDict[loc])
      
            index+=1
            
        self.strictInclusion=conjunction & disjunction
        
        self.linearCubeBDD= self.manager.ReadOne()
        for id in range(self.nloc):
            self.linearCubeBDD &= self.linearCubeArray[id]
                
  
    def computeSuccessorsBDD(self,sigmaBDD, locBDD):
        """
        Computes the set of successors of the set locBDD on label sigma
        (May be redundant with post(cell, sigma))
        """
        temp = self.transBDD & locBDD & sigmaBDD
        temp2=temp.ExistAbstract(self.labelsCubeBDD)
        temp3=temp2.ExistAbstract(self.locsCubeBDD)
        t_sigma_li=temp3.SwapVariables(self.locPrimedCubeArray,self.locCubeArray,self.locNLogVar)
        return t_sigma_li

    def computeSafe(self):
        """
        Computes the set of winning sets for objective Safe(SAFE)
        """
        if (self.safe==None):      
            F= [self.safeBDD]
            Fprevious=[]  
            niter=0
            while not (F == Fprevious):
                niter+=1
                Fprevious=F
                cpre, a=self.cpre(F)
                temp = self.antichainIntersection(cpre, [self.safeBDD])
                F= self.antichainIntersection( F, temp)
            self.safe=F
        return self.safe

    def computeSafeStrat(self, safeAntichain=None):
        """
        Computes the set of winning sets and a strategy for objective Safe(SAFE)
        """

        if (self.safe==None):  
            if safeAntichain==None:    
                safeAntichain= [self.safeBDD]
            F=safeAntichain
            Fprevious=[]  
            niter=0
            while not (F == Fprevious):
                niter+=1
                Fprevious=F
                cpre,a=self.cpre(F)
                temp = self.antichainIntersection(cpre, safeAntichain)
                F= self.antichainIntersection( F, temp)
            self.safe=F
        strat= self.computeSafetyStratFromAntichain(self.safe)
        return self.safe, strat
            
    def printSet(self, set ):
        """
        Pretty prints on the standard output the contents of a set of
        states
        """
        print "{",
        first=True
        for loc in self.BDDLocDict: 
           if imp(self.BDDLocDict[loc], set)==self.manager.ReadOne():
               if first :
                   first = False
               else:
                   print ", ",  
               print loc,
        print '}'
    
    def printAntichain(self, antichain):
        """
        Pretty prints on the standard output the contents of an
        antichain of sets of states
        """
        print "{"
        for set in antichain:
            print "   ", 
            self.printSet(set)
        print "}"
    
    def printSigma(self, sigma):
        """
        Prints on the standard output the contents of an
        set of labels
        """
        for lab in self.BDDLabelDict:
            if not (sigma & self.BDDLabelDict[lab]== ~self.manager.ReadOne()):
                print lab

def main(options, args):
    """
    The main function (although not the first to be called: 
    optionParsing is called first 
    """
    filename=args[0]
    startTimeParsing=time()
    gp=GameParser()
    gp.options=options
    game= gp.parse(filename)
    game.parser=gp
    startTimeInit=time()
    if not options.enumerative : 
        game.addLinearLocEncoding()
    game.options=options
##############################################################
    startTimeSolve=time()
    W,alpha= game.solve([game.targetBDD],[game.safeBDD])
    game.W=W
    if options.simplify:
        startTimeSimplify=time()
        alpha.simplify()
    finalTime=time()
    if options.time:
        print "    Parsing Time        : ",  startTimeInit - startTimeParsing , " s"
        print "    Initialization Time : ", startTimeSolve - startTimeInit, " s"
        if options.simplify:
            print "    Solving Time        : ", startTimeSimplify - startTimeSolve, " s"
            print "    Simplifying Time    : ", finalTime -startTimeSimplify 
        else :
            print "    Solving Time        : ", finalTime - startTimeSolve, " s"
        print "--------------------------"
        print "    Total Time          : ", finalTime - startTimeParsing, " s"
    print "Winning Cells :" 
    game.printAntichain(W)
    print "Strategy :"
    alpha.display()
    
    if not game.includedInAntichain(game.initBDD,W):
        print "The initial set is not winning"
        if options.interactive: 
            print "No strategy to play interactively" 
    else :
        print "The initial set is winning"
    
        if options.interactive:
            player= StrategyPlayer(game,alpha)
            player.cmdloop()

def optionParsing():
    """
    The first function called : parses the command line options
    """
    usage = "usage: %prog [options] file (type %prog -h for more help)"
    optionParser = OptionParser(usage)
    optionParser.add_option("-i", "--interactive", dest="interactive", action="store_true", default=False,
                      help="After computing a strategy, launch interactive strategy player")
    optionParser.add_option("-e","--enumerative", dest="enumerative", action="store_true", default=False,
                      help="Use the enumerative cpre in all computations")
    optionParser.add_option("-n","--notTotalize", dest="totalize", action="store_false", default=True,
                      help="Turn off the totalization of the transition relation")
    optionParser.add_option("-r", "--trace", dest="stackTrace", action="store_true", default=False,
                      help="Turn on the display of stack traces in case of error")    
    optionParser.add_option("-s","--simplify", dest="simplify", action="store_false", default=True,
                      help="Turn off the simplification of the strategies before display")
    optionParser.add_option("-t", "--time", dest="time", action="store_true", default=False,
                      help="Display computation times")        
    optionParser.add_option("-v", "--verbose",help="Display warnings",
                      action="store_true", dest="verbose",default=False)
    (options, args) = optionParser.parse_args()
    if len(args) != 1:
        optionParser.error("incorrect number of arguments")
    try :
        main(options, args)
    except  KeyboardInterrupt :
        print "\nBye !"
        quit()
    except SystemExit : 
        pass
    except : 
        if not options.stackTrace: 
            print "An unhandled interrupt provoked the shutting down of the program"
            print "Use -r option to turn on the display of Python stack trace"
            quit()
        else : 
            raise

if __name__=='__main__':
    optionParsing()
        
