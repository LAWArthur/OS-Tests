#include <pthread.h>
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

pthread_mutex_t lock;
pthread_cond_t ok_read, ok_write;
int ww, wr, aw, ar;

void monitor_init()
{
    pthread_mutex_init(&lock, NULL);
    pthread_cond_init(&ok_read, NULL);
    pthread_cond_init(&ok_write, NULL);
}

void reader_enter()
{
    pthread_mutex_lock(&lock);
    wr++;
    if(aw > 0){
        pthread_cond_wait(&ok_read, &lock);
    }
    wr--;
    ar++;
    pthread_mutex_unlock(&lock);
}

void reader_leave()
{
    pthread_mutex_lock(&lock);
    ar--;
    if(ar + wr == 0 && ww > 0){
        pthread_cond_signal(&ok_write);
    }
    pthread_mutex_unlock(&lock);
}

void writer_enter()
{
    pthread_mutex_lock(&lock);
    ww++;
    while(ar + wr > 0 || aw > 0){
        pthread_cond_wait(&ok_write, &lock);
    }
    ww--;
    aw++;
    pthread_mutex_unlock(&lock);
}

void writer_leave()
{
    pthread_mutex_lock(&lock);
    aw--;
    if(wr > 0) {
        pthread_cond_broadcast(&ok_read);
    }
    else if(ww > 0){
        pthread_cond_signal(&ok_write);
    }
    pthread_mutex_unlock(&lock);
}

void *reader(void *arg)
{
    int i = (int)arg;
    reader_enter();
    printf("reader %d entered, current ar = %d, current wr = %d, current aw = %d, current ww = %d\n", i, ar, wr, aw, ww);
    // random delay
    usleep(rand() % 1000000);
    printf("reader %d leaving, current ar = %d, current wr = %d, current aw = %d, current ww = %d\n", i, ar, wr, aw, ww);
    reader_leave();
    return NULL;
}

void *writer(void *arg)
{
    int i = (int)arg;
    writer_enter();
    printf("writer %d entered, current ar = %d, current wr = %d, current aw = %d, current ww = %d\n", i, ar, wr, aw, ww);
    //random delay
    usleep(rand() % 1000000);
    printf("writer %d leaving, current ar = %d, current wr = %d, current aw = %d, current ww = %d\n", i, ar, wr, aw, ww);
    writer_leave();
    return NULL;
}

// simple test program
int main()
{
    monitor_init();
    for(int i=0;i<10;i++){
        pthread_t r, w;
        pthread_create(&r, NULL, reader, (void*)i);
        pthread_create(&w, NULL, writer, (void*)i);
        //random delay
        usleep(rand() % 1000000);
    }
    pthread_exit(NULL);
    return 0;
}