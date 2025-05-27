#include <stdio.h>
#include <pthread.h>
#include <chrono>
#include <cstring>
#include <cstdlib>
#define N_ITERS 1000000
int n_procs;
double time_elps[64][N_ITERS];

void *thread_main(void * data){
    pthread_detach(pthread_self());
    int i = (unsigned long long)data;
    auto last_time = std::chrono::high_resolution_clock::now();
    double time_accum, time_max=0.0f, time_min=1e9;
    for(int j = 0;j < N_ITERS;j++){
        auto curr_time = std::chrono::high_resolution_clock::now();
        double time_elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(curr_time - last_time).count();
        time_accum += time_elapsed;
        if(time_elapsed > time_max) time_max = time_elapsed;
        if (time_elapsed < time_min) time_min = time_elapsed;
        time_elps[i][j] = time_elapsed;
        last_time = curr_time;
    }

    printf("thread %d exited. time_avg=%lf, time_max=%lf, time_min=%lf\n", i, time_accum / N_ITERS, time_max, time_min);
    char filename[256];
    sprintf(filename, "results/result%d", i);
    FILE* f = fopen(filename, "w");
    fwrite(time_elps[i], sizeof(double), N_ITERS, f);
    fclose(f);
    pthread_exit(NULL);
}

int main(int argc, char** argv){
    if(argc != 2)return 0;
    n_procs = atoi(argv[1]);
    for(int i=0;i<n_procs;i++){
        pthread_t _;
        int rc = pthread_create(&_, NULL, thread_main, (void *)i);
    }
    
    pthread_exit(NULL);
    return 0;
}