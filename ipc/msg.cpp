#include <sys/msg.h>
#include <sys/ipc.h>
#include <wait.h>
#include <unistd.h>
#include <stdio.h>
#include <chrono>

#define NUM_ITERS 1000000
#define MSG_KEY 323

struct msg_buf{
    long mtype;
    int data;
};

int main(){
    int msgqid = msgget(MSG_KEY, IPC_EXCL); 
    if(msgqid > 0){
        printf("Warning: msg queue exists\n");
        msgctl(msgqid, IPC_RMID, NULL);
    }
    msgqid = msgget(MSG_KEY, IPC_CREAT | 0666);
    if(msgqid < 0){
        printf("Error: failed to create msg queue\n");
    }

    int pid = fork(), ppid = 0, msgtype;
    struct msg_buf buf{0, 0};
    if(pid < 0){ 
        printf("Error: failed to create child\n");
        return -1;
    }
    auto st = std::chrono::steady_clock::now();
    if(pid == 0){ // child
        pid = getpid();
        ppid = getppid();
        msgtype = 1;
        buf.mtype = msgtype;
        buf.data = 1;
        msgsnd(msgqid, &buf, sizeof(buf.data), IPC_NOWAIT);
    }
    else {
        msgtype = 2;
    }

    while(buf.data <= NUM_ITERS){
        while(msgrcv(msgqid, &buf, sizeof(buf.data), 3 - msgtype, 0) < 0);
        buf.data += 1;
        // printf("%s recved %d\n", ppid?"CHILD":"PARENT", buf.data);
        buf.mtype = msgtype;
        // printf("%d\n", buf.data);
        msgsnd(msgqid, &buf, sizeof(buf.data), IPC_NOWAIT);
    }

    auto ed = std::chrono::steady_clock::now();
    double ts = std::chrono::duration<double>(ed - st).count();
    if(ppid){
        printf("Child exited, time %lf s, data %d\n", ts, buf.data);
    }
    else {
        wait(NULL);
        msgctl(msgqid, IPC_RMID, 0);
        printf("Parent exited, time %lf s, data %d\n", ts, buf.data);
    }
    return 0;
}