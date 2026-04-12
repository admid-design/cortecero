# /close-block

Genera el output de cierre formal del bloque activo.

## Instrucciones

Recopila toda la información del bloque activo y genera el output de cierre en el formato obligatorio de `AGENTS.md`.

Si algún campo no está disponible, dilo explícitamente — no lo inventes.

## Output obligatorio

```
Bloque: <nombre del bloque>
Tipo: IMPLEMENTATION | HARDENING | SPIKE | DEMO | DOCS
Objetivo: <qué resolvía este bloque en una frase>
Commit: <sha del commit en main, o PENDIENTE si no hay aún>

Alcance implementado:
  - <archivo/cambio 1>
  - <archivo/cambio 2>
  - ...

Archivos tocados:
  - <lista de archivos modificados o creados>

Validación ejecutada:
  - <qué se corrió> → <resultado>
  - <qué se corrió> → <resultado>

Resultado:
  <descripción del estado real tras el bloque>

Huecos:
  - <qué no se verificó o quedó pendiente>

Riesgos:
  - <qué no conviene afirmar basándose en este bloque>

Estado final: CERRADO_LOCAL | CERRADO_CON_EVIDENCIA_LOCAL | PROMULGADO | BLOQUEADO | PARCIAL
```

## Regla de honestidad

Si el estado es PARCIAL o BLOQUEADO, explica exactamente qué falta y por qué.
No declares PROMULGADO si el CI remoto no está en verde.
No declares CERRADO_CON_EVIDENCIA_LOCAL si el smoke o la evidencia real no se ejecutó.
