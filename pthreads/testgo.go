package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"os"
	"strconv"
	"sync"
	"time"
)

var n_procs int = 16

const N_ITERS int = 1000000

var time_elps [128][N_ITERS]float64

func worker(id int) {
	var time_accum float64 = 0
	var time_min float64 = 1000000000
	var time_max float64 = 0

	last_time := time.Now().UnixNano()
	for j := 0; j < N_ITERS; j++ {
		curr_time := time.Now().UnixNano()
		time_elapsed := float64(curr_time - last_time) // in accordance to c++ code
		last_time = curr_time
		time_accum += time_elapsed
		if time_elapsed < time_min {
			time_min = time_elapsed
		}
		if time_elapsed > time_max {
			time_max = time_elapsed
		}
		time_elps[id][j] = time_elapsed
	}

	buf := new(bytes.Buffer)
	err := binary.Write(buf, binary.LittleEndian, time_elps[id])
	if err != nil {
		fmt.Println("binary.Write failed:", err)
	}
	bytes := buf.Bytes()
	os.WriteFile(fmt.Sprintf("results/result%v", id), bytes, 0666)
	fmt.Printf("Goroutine %d exited. time_avg=%v, time_min=%v, time_max=%v\n", id, time_accum/float64(N_ITERS), time_min, time_max)

}

func main() {
	n_procs, _ = strconv.Atoi(os.Args[1])

	var wg sync.WaitGroup

	for i := 0; i < n_procs; i++ {
		wg.Add(1)

		go func() {
			defer wg.Done()
			worker(i)
		}()
	}

	wg.Wait()

}
