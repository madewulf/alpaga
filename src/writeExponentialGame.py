#!/usr/bin/env python
import sys

def isPrime(n):
    if n<2: return False
    else : 
        nroot=n**0.5
        i=2
        while (i<=nroot):
            if n%i == 0 :
                return False
            i=i+1
        return True

def primes(n):
    """ returns a list of n prime numbers"""
    nprime=0
    i=2
    res=[]
    while (nprime<n):
        if isPrime(i):
            res.append(i)
            nprime+=1
        i+=1
    return res

def writeComponentTrans(n,i,prime):
    for j in range(prime-1):
        for k in range(n):
            print "s%d_%d, s%d_%d, l%d"% (i,j+1, i,j+2, k+1) 
        print "s%d_%d, Bad, #"% (i,j+1)
    for k in range(i-1)+range(i,n):
        print "s%d_%d, s%d_%d, l%d"% (i,prime, i,1, k+1) 
    print "s%d_%d, Bad, l%d" % (i,prime,i)
    print "s%d_%d, Safe, #" %(i, prime)
def writeExpGame(n):
#    filename= "expgame"+ str(n)+'txt'
#    f=open(filename,"w")
    primeList = primes(n)
    print "ALPHABET : #, l1", 
    for i in range(2,n+1):
        print ", l%d" % i,
    print " "
    print "STATES : s0, Safe, Bad",
    i=1
    for prime in primeList:
        for j in range(prime):
            print ", s%d_%d" %(i,j+1),
        i+=1
    print " "
    print "INIT : s0"
    print "SAFE : s0, Safe",
    i=1
    for prime in primeList:
        for j in range(prime):
            print ", s%d_%d" %(i,j+1),
        i+=1
    print " "   
    i=1
    print "TRANS : "
    for i in range (n):
        for j in range(n):
            print "s0,s%d_1 ,l%d" % (i+1,j+1)
    print "s0, Bad, #"
    i=1
    for prime in primeList:
        writeComponentTrans(n,i,prime)
        i+=1
    for i in range(n):
        print "Safe,Bad, l%d" % (i+1)
    print "Safe, Safe, #"
    print "OBS :"
    print  "s0,Safe, Bad ",
    for i in range(n):
        for j in range(primeList[i]):
            print ", s%d_%d"% (i+1,j+1),
    print " " 
    
if __name__ == '__main__':
    writeExpGame(int(sys.argv[1]))