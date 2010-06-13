from pycudd import *
import pycudd
from math import log, ceil
import sys
import commands
from alpaga import *

class GameParser(object):

    def _init_(self):
        self.maxid=0
        self.manager = DdManager()
        self.manager.SetDefault()
    
    def printWarning(self,message):
        if  self.options.verbose : 
            print "*** Warning :",message
    def printError(self,message):
            print "*** Error :",message  
            quit()  

    def parse(self, fileName):

        addedVarNr=0
        maxid=0
        first = True
        addedCubeArray=DdArray(1)
        addedPrimeCubeArray=DdArray(1)
        f=open(fileName,'r')
        dictkeywords = {'ALPHABET':[] , 'STATES':[] , 'INIT':[], 'TARGET':[],'SAFE':[]}
        translist=[]
        obslist=[]
        priolist=[]
        mode ="normal"
        lineNumber=0
        nUsefulLine=0
        try : 

            for line in f:
                if not ( line.startswith("#") or line.strip()==""):
                    nUsefulLine+=1
                    line = line.split("#")[0].strip()#Comment suppression
                    if line.startswith('TRANS'):
                        mode ="trans"
                        continue
                    if line.startswith('OBS'):
                        mode ="obs"
                        continue
                    if mode == "normal":
                        foundKeyword=False 
                        for word in dictkeywords:

                            if line.startswith(word):
                                foundKeyword =True
                                line=line[len(word):].strip()
                                line=line[1:].strip()
                                dictkeywords[word] = line.split(',')
                                tmp=[]
                                for id in  dictkeywords[word]:
                                    if id.strip()!="":
                                        tmp.append(id.strip())
                                dictkeywords[word]=tmp
                        if not foundKeyword:
                            self.printError("Keyword unknown at line "+ str(lineNumber))
                    if mode == "obs":
                        tmp=line.split(":")
                        if (len(tmp)==1):
                            obslist.append(line.split(','))
                        else :
                            obslist.append(tmp[0].split(','))
                            priolist.append(int(tmp[1]))
                    if mode== 'trans' :
                        translist.append(line.split(','))
                    lineNumber+=1
        except RuntimeError, ValueError:
            self.printError(" in line : "+ lineNumber)
        if  nUsefulLine==0:
            self.printError(" Empty file ")
        try : 
            locSigmaTupleSet=set()
            destSet=set()
            for trans in translist : 
                for i in range(len(trans)):
                    trans[i]=trans[i].strip()
                locSigmaTupleSet.add((trans[0],trans[2]))
                destSet.add(trans[1])  
            # we check that the transition relation is total and
            #emit warnings if it is not the case
            sinkAdded =False
            for  state in dictkeywords['STATES']:
                if state not in destSet and state not in dictkeywords["INIT"]: 
                    self.printWarning("no transition to non initial state "+ state)
                thereIsATransition =False
                for label in dictkeywords['ALPHABET']:
                    if (state,label) not in locSigmaTupleSet :
#                        self.printWarning("no transition on "+ label + " for state "  +state)
                        if self.options.totalize : 
                            if not sinkAdded:
                                sinkAdded=True
                                #self.printWarning("SINK state added")
                                dictkeywords['STATES'].append("SINK")
                                for label2 in dictkeywords['ALPHABET']:
                                    translist.append(("SINK","SINK",label2))
                                    locSigmaTupleSet.add(("SINK",label2))
                                destSet.add("SINK")
                                obslist.append(["SINK"])
                                priolist.append(1)  
    
                            translist.append((state,"SINK",label))
                            #self.printWarning("transition "+state+", SINK, "+label + " added")
                    else : 
                        thereIsATransition =True
                if not thereIsATransition : 
                    self.printWarning("there is no transition outgoing from "  +state + " in the model")
                        
            unionOfObs=set()
            for obs in obslist : 
                for i in range(len(obs)):
                    obs[i]=obs[i].strip()
                s=set(obs)
                if s & unionOfObs != set():
                   self.printError("observation " + repr(obs)+ "has an intersection with another intersection" ) 
                else : 
                    unionOfObs |= s
            stateSet= set(dictkeywords['STATES'])
            if unionOfObs<stateSet:
                self.printError("Some states are in no observation : "+ repr(stateSet - unionOfObs))
            elif unionOfObs>stateSet:
                self.printError("Unknown state in an observation.")
            manager = DdManager()
            manager.SetDefault()
    
            BDDLocDict, locsCubeBDD, maxid, locCubeArray, locPrimedCubeArray= self.buildBDDFramework(dictkeywords['STATES'],manager,maxid,1)
            BDDLabelDict, labelsCubeBDD, maxid, labelCubeArray= self.buildBDDFramework(dictkeywords['ALPHABET'],manager,maxid,0)
            nloc=len(dictkeywords['STATES'])
            locsPrimedCubeBDD= locsCubeBDD.SwapVariables(locCubeArray,locPrimedCubeArray,self.nval2nvar(len(BDDLocDict)))
    
            locMask =~manager.ReadOne()
            for loc in BDDLocDict:
                locMask |= BDDLocDict[loc]
    
            transBDD=self.buildTransBDD(manager, translist,BDDLocDict,BDDLabelDict, locCubeArray, locPrimedCubeArray)
    
            initBDD= self.buildSetBDD(manager, BDDLocDict,dictkeywords["INIT"])
            targetBDD= self.buildSetBDD(manager, BDDLocDict,dictkeywords["TARGET"])
            safeBDD=self.buildSetBDD(manager,BDDLocDict,dictkeywords["SAFE"])
            
            obsBDDList=[]
            obsPrioDict={}
            prioBDDDict={}
            j=0
            maxprio=0
            for prio in priolist:
                if prio>maxprio:
                    maxprio=prio
                prioBDDDict[prio]=~manager.ReadOne()
            j=0
            for obs in obslist : 
                temp=self.buildSetBDD(manager, BDDLocDict, obs)
                obsBDDList.append(temp)
                if len(priolist)!=0:
                    obsPrioDict[temp]=priolist[j]
                    prioBDDDict[priolist[j]]|=temp
                j=j+1
                
            ga = Game()
            ga.manager=manager
            ga.BDDLocDict=BDDLocDict
            ga.locsCubeBDD=locsCubeBDD
            ga.locCubeArray=locCubeArray
            ga.locPrimedCubeArray=locPrimedCubeArray
            ga.BDDLabelDict= BDDLabelDict
            ga.labelsCubeBDD=labelsCubeBDD
            ga.maxid=maxid
            ga.labelCubeArray= labelCubeArray
            ga.nloc=nloc
            ga.locsPrimedCubeBDD=locsPrimedCubeBDD
            ga.locMask=locMask
            ga.transBDD=transBDD
            ga.initBDD=initBDD
            ga.targetBDD=targetBDD
            ga.safeBDD=safeBDD
            ga.obsBDDList= obsBDDList
            ga.locNLogVar=self.nval2nvar(len(BDDLocDict))
            ga.obsPrioDict=obsPrioDict
            ga.prioBDDDict=prioBDDDict
            ga.maxPriority=maxprio
        except RuntimeError:
            printError(" in line : " + lineNumber)
            quit()
        return ga

    def nval2nvar(self, nval):
        """
        computes the number of binary variables needed to represent nval different values
        >>> [nval2nvar(i) for i in [0,1,2,3,67]]
        [0, 1, 1, 2, 7]
        """
        if (nval==0):
            return 0
        else :
            return int(ceil(log(nval)/log(2)))

    def buildBDDFramework(self, idList, manager, maxid, primed=False):
        """
        Builds the needed dictionaries, cubes and arrays to manipulate
        the ids in idList as BDDs
        """
        nid =len(idList)
        nvar= self.nval2nvar(nid)
        idCubeArray= DdArray(nid)
        if primed:
            idPrimedCubeArray= DdArray(nid)
        varList=[]
        primeVarList=[]
        for id in range(nvar):
            varList.append(manager.IthVar(maxid))
            idCubeArray[id]=manager.IthVar(maxid)
            maxid=maxid+1
            if primed:
                primeVarList.append(manager.IthVar(maxid))
                idPrimedCubeArray[id]=manager.IthVar(maxid)
                maxid=maxid+1
        BDDIdDict={}
        for i in range(nid):
            itmp=i
            varBDD=manager.ReadOne()
            for j in range(nvar):
                if itmp % 2 == 0:
                    varBDD &= ~varList[j]
                else:
                    varBDD &=varList[j]
                itmp = itmp/2
            BDDIdDict[idList[i]]=varBDD

        idCubeBDD= manager.ReadOne()
        for id in range(nvar):
            idCubeBDD &= idCubeArray[id]


        if primed :
            return BDDIdDict, idCubeBDD, maxid, idCubeArray, idPrimedCubeArray
        else:
            return BDDIdDict, idCubeBDD, maxid, idCubeArray

    def buildTransBDD(self, manager, translist,BDDStateDict,BDDLabelDict, stateCubeArray, statePrimedCubeArray):
        transBDD= ~manager.ReadOne()
        for trans in translist :
            #print (trans)
            try : 
                src=BDDStateDict[trans[0]]
            except KeyError:
                self.printError("name unknown : " + trans[0])
            try:
                dest=BDDStateDict[trans[1]]
            except KeyError:
                self.printError( "name unknown : "+ trans[1])
            try : 
                label=BDDLabelDict[trans[2]]
            except KeyError : 
                self.printError("name unknown : "+ trans[2])
                quit()
                
            dest=dest.SwapVariables(stateCubeArray,statePrimedCubeArray,self.nval2nvar(len(BDDStateDict)))
            transBDD |= (src & dest & label)
        return transBDD

    def buildSetBDD(self, manager, BDDStateDict,stateIdList):
        """
        Build a set from a list id state ID
        """
        set = ~manager.ReadOne()
        for i in range(len(stateIdList)):
            try : 
                set |= BDDStateDict[stateIdList[i]]
            except KeyError : 
                self.printError( "name unknown : " +stateIdList[i]) 
        return set

def checkargs():
    if not(len(sys.argv)==2):
        usage()
        quit()

def usage():
    print "usage : python parser.py filename"

def main():
    checkargs()
    filename=sys.argv[1]
    print filename
    gp=GameParser()

    game= gp.parse(filename)
    
if __name__=='__main__':
    main()
