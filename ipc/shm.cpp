#include <sys/shm.h>
#include <sys/ipc.h>
#include <wait.h>
#include <unistd.h>
#include <stdio.h>
#include <chrono>
#include <linux/sched.h>

#define NUM_ITERS 1000000
#define MSG_KEY 323
#define I_CHILD 0x13131313
#define I_PARENT 0x24242424

int main(int argc, char** argv){
    int key, shmid;
    int volatile *data;
    int last_sent;

    key = ftok(argv[0], MSG_KEY);
    if(key < 0){
        printf("Error: ftok failed\n");
        return -1;
    }

    int pid = fork(), ppid = 0;
    if(pid < 0){ 
        printf("Error: failed to create child\n");
        return -1;
    }
    auto st = std::chrono::steady_clock::now();
    if(pid == 0){ // child
        pid = getpid();
        ppid = getppid();
        
        shmid = shmget(key, sizeof(int), IPC_CREAT | 0666);
        if(shmid < 0){
            printf("Error: CHILD: shmget failed\n");
            return -1;
        }
        data = (int *)shmat(shmid, NULL, 0);
        printf("%p\n", data);
        *data = I_CHILD;
        while(*data != I_PARENT); // 简单握手，确认信道建立
        last_sent = 1;
        *data = 1;
        printf("CHILD: ACK Recved, established! %x\n", last_sent);
    }
    else {
        shmid = shmget(key, sizeof(int), IPC_CREAT | 0666);
        if(shmid < 0){
            printf("Error: CHILD: shmget failed\n");
            return -1;
        }
        data = (int *)shmat(shmid, NULL, 0);
        printf("%p\n", data);
        while(*data != I_CHILD);
        *data = I_PARENT;
        last_sent = I_PARENT;
        printf("PARENT: SEQ Recved, established! %x\n", last_sent);
    }
    
    do {
        while(*data == last_sent);
        last_sent = *data;
        last_sent += 1;
        *data = last_sent;
    }
    while(last_sent <= NUM_ITERS);

    auto ed = std::chrono::steady_clock::now();
    double ts = std::chrono::duration<double>(ed - st).count();
    if(ppid){
        printf("Child exited, time %lf s, data %d\n", ts, last_sent);
        shmdt((void *)data);
    }
    else {
        shmdt((void *)data);
        wait(NULL);
        shmctl(shmid, IPC_RMID, 0);
        printf("Parent exited, time %lf s, data %d\n", ts, last_sent);
    }
    return 0;
}