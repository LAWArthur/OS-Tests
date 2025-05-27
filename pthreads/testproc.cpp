#include <stdio.h>
#include <unistd.h>
#include <chrono>
#include <cstring>
#include <cstdlib>
#include <wait.h>
#define N_ITERS 1000000
int n_procs, i;
double time_elps[N_ITERS];

int main(int argc, char** argv){
    if(argc != 2)return 0;
    n_procs = atoi(argv[1]);
    for(i=0;i<n_procs-1;i++){
        int pid = fork();
        if(pid == 0)break;
    }
    auto last_time = std::chrono::high_resolution_clock::now();
    double time_accum, time_max=0.0f, time_min=1e9;
    for(int j = 0;j < N_ITERS;j++){
        auto curr_time = std::chrono::high_resolution_clock::now();
        double time_elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(curr_time - last_time).count();
        time_accum += time_elapsed;
        if(time_elapsed > time_max) time_max = time_elapsed;
        if (time_elapsed < time_min) time_min = time_elapsed;
        time_elps[j] = time_elapsed;
        last_time = curr_time;
    }

    printf("process %d exited. time_avg=%lf, time_max=%lf, time_min=%lf\n", i, time_accum / N_ITERS, time_max, time_min);
    char filename[256];
    sprintf(filename, "results/result%d", i);
    FILE* f = fopen(filename, "w");
    fwrite(time_elps, sizeof(double), N_ITERS, f);
    fclose(f);
    if(i == n_procs - 1){
        while(wait(NULL) >= 0);
    }
    return 0;
}