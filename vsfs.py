#! /usr/bin/env python

# TODO: Read operations should check updates in transaction

from __future__ import print_function
import random
from optparse import OptionParser
from copy import deepcopy

# to make Python2 and Python3 act the same -- how dumb
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

DEBUG = False

def dprint(str):
    if DEBUG:
        print(str)

printOps      = True
printState    = True
printFinal    = True

class bitmap:
    def __init__(self, fs: 'fs',  size):
        self.size = size
        self.bmap = []
        for num in range(size):
            self.bmap.append(0)
        self.numAllocated = 0
        self.fs = fs
    
    def copy(self):
        clone = bitmap(self.fs, self.size)
        clone.bmap = self.bmap.copy()
        clone.numAllocated = self.numAllocated
        return clone

    def alloc(self): # Write
        self = self.fs.makeTransaction(self)

        for num in range(len(self.bmap)):
            if self.bmap[num] == 0:
                self.bmap[num] = 1
                self.numAllocated += 1

                return num
        return -1

    def free(self, num): # Write
        self = self.fs.makeTransaction(self)

        assert(self.bmap[num] == 1)
        self.numAllocated -= 1
        self.bmap[num] = 0

    def markAllocated(self, num): # Write
        self = self.fs.makeTransaction(self)

        assert(self.bmap[num] == 0)
        self.numAllocated += 1
        self.bmap[num] = 1

    def numFree(self):
        return self.size - self.numAllocated

    def dump(self):
        s = ''
        for i in range(len(self.bmap)):
            s += str(self.bmap[i])
        return s

class block:
    def __init__(self, fs: 'fs', ftype):
        assert(ftype == 'd' or ftype == 'f' or ftype == 'free')
        self.ftype = ftype
        # only for directories, properly a subclass but who cares
        self.dirUsed = 0
        self.maxUsed = 32
        self.dirList = []
        self.data    = ''
        self.fs = fs

    def copy(self):
        clone = block(self.fs, self.ftype)
        clone.dirUsed = self.dirUsed
        clone.maxUsed = self.maxUsed
        clone.dirList = self.dirList.copy()
        clone.data    = self.data
        return clone

    def dump(self):
        if self.ftype == 'free':
            return '[]'
        elif self.ftype == 'd':
            rc = ''
            for d in self.dirList:
                # d is of the form ('name', inum)
                short = '(%s,%s)' % (d[0], d[1])
                if rc == '':
                    rc = short
                else:
                    rc += ' ' + short
            return '['+rc+']'
            # return '%s' % self.dirList
        else:
            return '[%s]' % self.data

    def setType(self, ftype):
        assert(self.ftype == 'free')
        self.ftype = ftype

    def addData(self, data): # Write
        self = self.fs.makeTransaction(self)
        assert(self.ftype == 'f')
        self.data = data

    def getNumEntries(self):
        assert(self.ftype == 'd')
        return self.dirUsed

    def getFreeEntries(self):
        assert(self.ftype == 'd')
        return self.maxUsed - self.dirUsed

    def getEntry(self, num):
        assert(self.ftype == 'd')
        assert(num < self.dirUsed)
        return self.dirList[num]

    def addDirEntry(self, name, inum): # Write
        self = self.fs.makeTransaction(self)
        assert(self.ftype == 'd')
        self.dirList.append((name, inum))
        self.dirUsed += 1
        assert(self.dirUsed <= self.maxUsed)

    def delDirEntry(self, name): # Write
        self = self.fs.makeTransaction(self)
        assert(self.ftype == 'd')
        tname = name.split('/')
        dname = tname[len(tname) - 1]
        for i in range(len(self.dirList)):
            if self.dirList[i][0] == dname:
                self.dirList.pop(i)
                self.dirUsed -= 1
                return
        assert(1 == 0)

    def dirEntryExists(self, name):
        assert(self.ftype == 'd')
        for d in self.dirList:
            if name == d[0]:
                return True
        return False

    def free(self): # Write, no reference
        self = self.fs.makeTransaction(self)
        assert(self.ftype != 'free')
        if self.ftype == 'd':
            # check for only dot, dotdot here
            assert(self.dirUsed == 2)
            self.dirUsed = 0
        self.data  = ''
        self.ftype = 'free'

class inode:
    def __init__(self, fs: 'fs', ftype='free', addr=-1, refCnt=1):
        assert(ftype == 'd' or ftype == 'f' or ftype == 'free')
        self.ftype  = ftype
        self.addr   = addr
        self.refCnt = refCnt
        self.fs = fs
    
    def copy(self):
        clone = inode(self.fs, self.ftype, self.addr, self.refCnt)
        return clone

    def setAll(self, ftype, addr, refCnt): # Write
        self = self.fs.makeTransaction(self)
        assert(ftype == 'd' or ftype == 'f' or ftype == 'free')
        self.ftype  = ftype
        self.addr   = addr
        self.refCnt = refCnt

    def incRefCnt(self): # Write
        self = self.fs.makeTransaction(self)
        self.refCnt += 1

    def decRefCnt(self): # Write
        self = self.fs.makeTransaction(self)
        self.refCnt -= 1

    def getRefCnt(self):
        return self.refCnt

    def setType(self, ftype): # Write
        self = self.fs.makeTransaction(self)
        assert(ftype == 'd' or ftype == 'f' or ftype == 'free')
        self.ftype = ftype

    def setAddr(self, block): # Write
        self = self.fs.makeTransaction(self)
        self.addr = block

    def getSize(self):
        if self.addr == -1:
            return 0
        else:
            return 1

    def getAddr(self):
        return self.addr

    def getType(self):
        return self.ftype

    def free(self): # Write
        self = self.fs.makeTransaction(self)
        self.ftype = 'free'
        self.addr  = -1

    def dump(self):
        ftype = self.getType()
        if ftype == 'free':
            return '[]'
        else:
            return '[%s a:%s r:%d]' % (ftype, self.getAddr(), self.getRefCnt())

class Transaction:
    def __init__(self) -> None:
        self.changes: 'dict[tuple[str, int], bitmap | block | inode]' = {}
        
    def add(self, type, num, data):
        self.changes[(type, num)] = data
    
    def apply(self, fs: 'fs'):
        for (type, num), data in self.changes.items():
            if type == 'ibitmap':
                fs.ibitmap = data
            elif type == 'dbitmap':
                fs.dbitmap = data
            elif type == 'inode':
                fs.inodes[num] = data
            elif type == 'block':
                fs.data[num] = data
    
    def dump(self):
        return ' '.join(
            [(f'{type}' + (f'[{num}]' if type not in ['ibitmap', 'dbitmap'] else '') + f'->{data.dump()}')  for (type, num), data in self.changes.items()]
        )

class fs:
    def __init__(self, numInodes, numData):
        self.numInodes = numInodes
        self.numData   = numData
        
        self.ibitmap = bitmap(self, self.numInodes)
        self.inodes : 'list[inode]'  = []
        for i in range(self.numInodes):
            self.inodes.append(inode(self))

        self.dbitmap = bitmap(self, self.numData)
        self.data : 'list[block]'  = []
        for i in range(self.numData):
            self.data.append(block(self, 'free'))

        self.journal: 'list[Transaction]' = []

        self.currentTransaction = None

        # root inode
        self.ROOT = 0

        # create root directory
        self.beginTransaction()
        self.ibitmap.markAllocated(self.ROOT)
        self.inodes[self.ROOT].setAll('d', 0, 2)
        self.dbitmap.markAllocated(self.ROOT)
        self.data[0].setType('d')
        self.data[0].addDirEntry('.',  self.ROOT)
        self.data[0].addDirEntry('..', self.ROOT)
        self.endTransaction()
        self.executeTransactions()

        # these is just for the fake workload generator
        self.files      = []
        self.dirs       = ['/']
        self.nameToInum = {'/':self.ROOT}

    def dump(self):
        print('inode bitmap ', self.ibitmap.dump())
        print('inodes       ', end='')
        for i in range(0,self.numInodes):
            # ftype = self.inodes[i].getType()
            # if ftype == 'free':
            #     print('[]', end='')
            # else:
            #     print('[%s a:%s r:%d]' % (ftype, self.inodes[i].getAddr(), self.inodes[i].getRefCnt()), end='')
            print(self.inodes[i].dump(), end='')
        print('')
        print('data bitmap  ', self.dbitmap.dump())
        print('data         ', end='')
        for i in range(self.numData):
            print(self.data[i].dump(), end='')
        print('')

    def makeName(self):
        p = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'j', 'k', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']
        return p[int(random.random() * len(p))]
        p = ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 's', 't', 'v', 'w', 'x', 'y', 'z']
        f = p[int(random.random() * len(p))]
        p = ['a', 'e', 'i', 'o', 'u']
        s = p[int(random.random() * len(p))]
        p = ['b', 'c', 'd', 'f', 'g', 'j', 'k', 'l', 'm', 'n', 'p', 's', 't', 'v', 'w', 'x', 'y', 'z']
        l = p[int(random.random() * len(p))]
        return '%c%c%c' % (f, s, l)

    def inodeAlloc(self):
        return self.ibitmap.alloc()

    def inodeFree(self, inum):
        self.ibitmap.free(inum)
        self.inodes[inum].free()

    def dataAlloc(self):
        return self.dbitmap.alloc()

    def dataFree(self, bnum):
        self.dbitmap.free(bnum)
        self.data[bnum].free()
        
    def getParent(self, name):
        tmp = name.split('/')
        if len(tmp) == 2:
            return '/'
        pname = ''
        for i in range(1, len(tmp)-1):
            pname = pname + '/' + tmp[i]
        return pname

    def beginTransaction(self):
        # assert(self.currentTransaction is None) # if last transaction is still open, this means transaction failed, and should not be added to journal. 
        self.currentTransaction = Transaction()
    
    def endTransaction(self):
        assert(self.currentTransaction is not None)
        if printState:
            print("Transaction committed:")
            print(self.currentTransaction.dump())
        self.journal.append(self.currentTransaction)
        self.currentTransaction = None

    def makeTransaction(self, data):
        assert(self.currentTransaction is not None)
        if isinstance(data, bitmap):
            if data == self.ibitmap:
                type = 'ibitmap'
            elif data == self.dbitmap:
                type = 'dbitmap'
            else: raise ValueError()
            i = 0
        elif isinstance(data, inode):
            i = self.inodes.index(data)
            type = 'inode'
        elif isinstance(data, block):
            i = self.data.index(data)
            type = 'block'
        else : raise ValueError()
        
        if (type, i) not in self.currentTransaction.changes:
            self.currentTransaction.add(type, i, data.copy())
        return self.currentTransaction.changes[(type, i)]

    def executeTransactions(self):
        for transaction in self.journal:
            transaction.apply(self)
        self.journal = []

    def deleteFile(self, tfile):
        if printOps:
            print('unlink("%s");' % tfile)

        self.beginTransaction()

        inum = self.nameToInum[tfile]
        ftype = self.inodes[inum].getType()

        if self.inodes[inum].getRefCnt() == 1:
            # free data blocks first
            dblock = self.inodes[inum].getAddr()
            if dblock != -1:
                self.dataFree(dblock)
            # then free inode
            self.inodeFree(inum)
        else:
            self.inodes[inum].decRefCnt()

        # remove from parent directory
        parent = self.getParent(tfile)
        # print('--> delete from parent', parent)
        pinum = self.nameToInum[parent]
        # print('--> delete from parent inum', pinum)
        pblock = self.inodes[pinum].getAddr()
        # FIXED BUG: DECREASE PARENT INODE REF COUNT if needed (thanks to Srinivasan Thirunarayanan)
        if ftype == 'd':
            self.inodes[pinum].decRefCnt()
        # print('--> delete from parent addr', pblock)
        self.data[pblock].delDirEntry(tfile)

        # finally, remove from files list
        self.files.remove(tfile)

        self.endTransaction()
        return 0

    def createLink(self, target, newfile, parent):
        self.beginTransaction()

        # find info about parent
        parentInum = self.nameToInum[parent]

        # is there room in the parent directory?
        pblock = self.inodes[parentInum].getAddr()
        if self.data[pblock].getFreeEntries() <= 0:
            dprint('*** createLink failed: no room in parent directory ***')
            return -1

        # print('is %s in directory %d' % (newfile, pblock))
        if self.data[pblock].dirEntryExists(newfile):
            dprint('*** createLink failed: not a unique name ***')
            return -1

        # now, find inumber of target
        tinum = self.nameToInum[target]
        self.inodes[tinum].incRefCnt()

        # DONT inc parent ref count - only for directories
        # self.inodes[parentInum].incRefCnt()

        # now add to directory
        tmp = newfile.split('/')
        ename = tmp[len(tmp)-1]
        self.data[pblock].addDirEntry(ename, tinum)

        self.endTransaction()
        return tinum

    def createFile(self, parent, newfile, ftype):
        self.beginTransaction()

        # find info about parent
        parentInum = self.nameToInum[parent]

        # is there room in the parent directory?
        pblock = self.inodes[parentInum].getAddr()
        if self.data[pblock].getFreeEntries() <= 0:
            dprint('*** createFile failed: no room in parent directory ***')
            return -1

        # have to make sure file name is unique
        block = self.inodes[parentInum].getAddr()
        # print('is %s in directory %d' % (newfile, block))
        if self.data[block].dirEntryExists(newfile):
            dprint('*** createFile failed: not a unique name ***')
            return -1
        
        # find free inode
        inum = self.inodeAlloc()
        if inum == -1:
            dprint('*** createFile failed: no inodes left ***')
            return -1
        
        # if a directory, have to allocate directory block for basic (., ..) info
        fblock = -1
        if ftype == 'd':
            refCnt = 2
            fblock = self.dataAlloc()
            if fblock == -1:
                dprint('*** createFile failed: no data blocks left ***')
                self.inodeFree(inum)
                return -1
            else:
                self.data[fblock].setType('d')
                self.data[fblock].addDirEntry('.',  inum)
                self.data[fblock].addDirEntry('..', parentInum)
        else:
            refCnt = 1
            
        # now ok to init inode properly
        self.inodes[inum].setAll(ftype, fblock, refCnt)

        # inc parent ref count if this is a directory
        if ftype == 'd':
            self.inodes[parentInum].incRefCnt()

        # and add to directory of parent
        self.data[pblock].addDirEntry(newfile, inum)

        self.endTransaction()
        return inum

    def writeFile(self, tfile, data):
        self.beginTransaction()

        inum = self.nameToInum[tfile]
        curSize = self.inodes[inum].getSize()
        dprint('writeFile: inum:%d cursize:%d refcnt:%d' % (inum, curSize, self.inodes[inum].getRefCnt()))
        if curSize == 1:
            dprint('*** writeFile failed: file is full ***')
            return -1
        fblock = self.dataAlloc()
        if fblock == -1:
            dprint('*** writeFile failed: no data blocks left ***')
            return -1
        else:
            self.data[fblock].setType('f')
            self.data[fblock].addData(data)
        self.inodes[inum].setAddr(fblock)
        if printOps:
            print('fd=open("%s", O_WRONLY|O_APPEND); write(fd, buf, BLOCKSIZE); close(fd);' % tfile)

        self.endTransaction()
        return 0
            
    def doDelete(self):
        dprint('doDelete')
        if len(self.files) == 0:
            return -1
        dfile = self.files[int(random.random() * len(self.files))]
        dprint('try delete(%s)' % dfile)
        return self.deleteFile(dfile)

    def doLink(self):
        dprint('doLink')
        if len(self.files) == 0:
            return -1
        parent = self.dirs[int(random.random() * len(self.dirs))]
        nfile = self.makeName()

        # pick random target
        target = self.files[int(random.random() * len(self.files))]
        # MUST BE A FILE, not a DIRECTORY (this will always be true here)

        # get full name of newfile
        if parent == '/':
            fullName = parent + nfile
        else:
            fullName = parent + '/' + nfile

        dprint('try createLink(%s %s %s)' % (target, nfile, parent))
        inum = self.createLink(target, nfile, parent)
        if inum >= 0:
            self.files.append(fullName)
            self.nameToInum[fullName] = inum
            if printOps:
                print('link("%s", "%s");' % (target, fullName))
            return 0
        return -1
    
    def doCreate(self, ftype):
        dprint('doCreate')
        parent = self.dirs[int(random.random() * len(self.dirs))]
        nfile = self.makeName()
        if ftype == 'd':
            tlist = self.dirs
        else:
            tlist = self.files

        if parent == '/':
            fullName = parent + nfile
        else:
            fullName = parent + '/' + nfile

        dprint('try createFile(%s %s %s)' % (parent, nfile, ftype))
        inum = self.createFile(parent, nfile, ftype)
        if inum >= 0:
            tlist.append(fullName)
            self.nameToInum[fullName] = inum
            if parent == '/':
                parent = ''
            if ftype == 'd':
                if printOps:
                    print('mkdir("%s/%s");' % (parent, nfile))
            else:
                if printOps:
                    print('creat("%s/%s");' % (parent, nfile))
            return 0
        return -1

    def doAppend(self):
        dprint('doAppend')
        if len(self.files) == 0:
            return -1
        afile = self.files[int(random.random() * len(self.files))]
        dprint('try writeFile(%s)' % afile)
        data = chr(ord('a') + int(random.random() * 26))
        rc = self.writeFile(afile, data)
        return rc

    def run(self, numRequests):
        self.percentMkdir  = 0.40
        self.percentWrite  = 0.40
        self.percentDelete = 0.20
        self.numRequests   = 20

        print('Initial state')
        print('')
        self.dump()
        print('')
        
        for i in range(numRequests):
            if printOps == False:
                print('Which operation took place?')
            rc = -1
            while rc == -1:
                r = random.random()
                if r < 0.3:
                    rc = self.doAppend()
                    dprint('doAppend rc:%d' % rc)
                elif r < 0.5:
                    rc = self.doDelete()
                    dprint('doDelete rc:%d' % rc)
                elif r < 0.7:
                    rc = self.doLink()
                    dprint('doLink rc:%d' % rc)
                else:
                    if random.random() < 0.75:
                        rc = self.doCreate('f')
                        dprint('doCreate(f) rc:%d' % rc)
                    else:
                        rc = self.doCreate('d')
                        dprint('doCreate(d) rc:%d' % rc)
                if self.ibitmap.numFree() == 0:
                    print('File system out of inodes; rerun with more via command-line flag?')
                    exit(1)
                if self.dbitmap.numFree() == 0:
                    print('File system out of data blocks; rerun with more via command-line flag?')
                    exit(1)
            if printState == True:
                print(f'{len(self.journal)} transactions pending.')
            self.executeTransactions()
            if printState == True:
                print('')
                self.dump()
                print('')
            else:
                print('')
                print('  State of file system (inode bitmap, inodes, data bitmap, data)?')
                print('')

        if printFinal:
            print('')
            print('Summary of files, directories::')
            print('')
            print('  Files:      ', self.files)
            print('  Directories:', self.dirs)
            print('')

#
# main program
#
parser = OptionParser()

parser.add_option('-s', '--seed',        default=0,     help='the random seed',                      action='store', type='int', dest='seed')
parser.add_option('-i', '--numInodes',   default=8,     help='number of inodes in file system',      action='store', type='int', dest='numInodes') 
parser.add_option('-d', '--numData',     default=8,     help='number of data blocks in file system', action='store', type='int', dest='numData') 
parser.add_option('-n', '--numRequests', default=10,    help='number of requests to simulate',       action='store', type='int', dest='numRequests')
parser.add_option('-r', '--reverse',     default=False, help='instead of printing state, print ops', action='store_true',        dest='reverse')
parser.add_option('-p', '--printFinal',  default=False, help='print the final set of files/dirs',    action='store_true',        dest='printFinal')
parser.add_option('-c', '--compute',     default=False, help='compute answers for me',               action='store_true',        dest='solve')

(options, args) = parser.parse_args()

print('ARG seed',        options.seed)
print('ARG numInodes',   options.numInodes)
print('ARG numData',     options.numData)
print('ARG numRequests', options.numRequests)
print('ARG reverse',     options.reverse)
print('ARG printFinal',  options.printFinal)
print('')

random_seed(options.seed)

if options.reverse:
    printState = False
    printOps   = True
else:
    printState = True
    printOps   = False

if options.solve:
    printOps   = True
    printState = True

printFinal = options.printFinal

#
# have to generate RANDOM requests to the file system
# that are VALID!
#

f = fs(options.numInodes, options.numData)

#
# ops: mkdir rmdir : create delete : append write
#

f.run(options.numRequests)

