using LinearAlgebra
using Printf
using Random
using Statistics

function benchmark()
    BLAS.set_num_threads(1)
    Threads.nthreads() == 1 || error("Run Julia with one thread.")
    n = 512
    rng = MersenneTwister(42)
    matrix = randn(rng, n, n) + n * I
    rhs = matrix * ones(n)
    matrix \ rhs
    samples = Float64[]
    residual = 0.0
    for _ in 1:7
        GC.gc()
        elapsed = @elapsed begin
            solution = matrix \ rhs
        end
        residual = norm(matrix * solution - rhs) / norm(rhs)
        residual < 1.0e-12 || error("The linear solve failed its residual check.")
        push!(samples, elapsed)
    end
    sha = get(ENV, "CI_COMMIT_SHA", repeat("0", 40))
    occursin(r"^[0-9a-f]{40}$", sha) || error("Invalid commit SHA.")
    mkpath("results")
    open("results/benchmark.json", "w") do output
        @printf(output, "{\"schema\":1,\"name\":\"julia_linear_solve_512\",\"unit\":\"seconds\",\"value\":%.17g,", median(samples))
        @printf(output, "\"samples\":[%s],\"residual\":%.17g,", join(samples, ","), residual)
        @printf(output, "\"sha\":\"%s\",\"julia_version\":\"%s\",\"threads\":1,\"blas_threads\":1,", sha, VERSION)
        @printf(output, "\"cpu\":%s,\"blas\":%s}\n", repr(Sys.CPU_NAME), repr(string(BLAS.get_config())))
    end
    open("results/benchmark-action.json", "w") do output
        name = "linear_solve_512/$(Sys.CPU_NAME)/Julia-$(VERSION)/BLAS-$(BLAS.vendor())/threads-1"
        @printf(output, "[{\"name\":%s,\"unit\":\"seconds\",\"value\":%.17g}]\n", repr(name), median(samples))
    end
    println("Median linear solve time, ", median(samples), " seconds.")
end

benchmark()
