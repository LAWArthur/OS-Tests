#include <unistd.h>
#include <wait.h>
#include <stdio.h>
#include <chrono>

#define NUM_ITERS 1000000

int main(){
    int pipe1[2], pipe2[2], pipefd[2];
    if(pipe(pipe1)){
        printf("Error: failed to create pipe\n");
    }

    if(pipe(pipe2)){
        printf("Error: failed to create pipe\n");
    }

    int pid = fork(), ppid = 0, data = 1;
    if(pid < 0){ 
        printf("Error: failed to create child\n");
        return -1;
    }
    auto st = std::chrono::steady_clock::now();
    if(pid == 0){ // child
        pid = getpid();
        ppid = getppid();
        close(pipe1[1]);
        close(pipe2[0]);
        pipefd[0] = pipe1[0];
        pipefd[1] = pipe2[1];
        write(pipefd[1], &data, sizeof(int));
    }
    else {
        close(pipe2[1]);
        close(pipe1[0]);
        pipefd[0] = pipe2[0];
        pipefd[1] = pipe1[1];
    }

    while(data <= NUM_ITERS){
        read(pipefd[0], &data, sizeof(int));
        data += 1;
        write(pipefd[1], &data, sizeof(int));
    }

    auto ed = std::chrono::steady_clock::now();
    double ts = std::chrono::duration<double>(ed - st).count();
    if(ppid){
        printf("Child exited, time %lf s, data %d\n", ts, data);
    }
    else {
        wait(NULL);
        printf("Parent exited, time %lf s, data %d\n", ts, data);
    }
    return 0;
}