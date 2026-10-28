#!/usr/bin/env bash
# Entrena el ensemble completo (3 modelos de texto + 3 de vinculacion, semillas distintas).
#   bash train_all.sh            # mide en validacion real (modelos de prueba)
#   bash train_all.sh --with-val # incluye validacion
#   bash train_all.sh --with-val --with-holdout   # version FINAL (incluye tambien el examen independiente)
set -e
FLAG="$@"
for i in 1 2 3; do
  SUF=$([ "$i" = "1" ] && echo "" || echo "$i")
  python3 train_text.py --seed $((6 + i)) --out models/text_clf$SUF $FLAG
  python3 train_link.py --seed $((6 + i)) --out models/link$SUF $FLAG
done
echo "ensemble listo en models/"
