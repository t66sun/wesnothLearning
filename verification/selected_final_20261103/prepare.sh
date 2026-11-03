set -eu
root=/home/tongshu/acceptance/selected_final_20261103
mkdir "$root"
tar -xzf "$root.tar.gz" -C "$root"
cd "$root"
ln -s /home/tongshu/myDev/wesnothLearning/WesnothLearning/rules data/rules
mkdir -p .runtime
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
sha256sum "$root.tar.gz" .runtime/entropy.so data/rules/1.18.8-training/rules.json > identities.txt
export PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
/home/tongshu/venv/bin/python -u -m tests.acceptance_selected_final /home/tongshu/myDev/wesnothLearning/acceptance_20261031_astra/src/runs/l1-20261031b/a/duel "$root/observed" ea449f711877b2966598fee1a014f488ad4d6f20
