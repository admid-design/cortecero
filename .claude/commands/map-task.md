# /map-task

Mapea una petición o idea a un bloque concreto y accionable.

## Instrucciones

El usuario te dará una petición, idea o problema.
Tu trabajo es traducirlo a un bloque bien definido antes de implementar nada.

Devuelve exactamente esto:

```
Bloque: <nombre del bloque, formato AREA-CONCEPTO-NNN>
Tipo: IMPLEMENTATION | HARDENING | SPIKE | DEMO | DOCS
Objetivo: <qué resuelve en una frase>
Invariantes: <qué no puede romperse>
Alcance:
  - <qué está dentro>
  - <qué está dentro>
NO alcance:
  - <qué está explícitamente fuera>
Definition of done:
  - <criterio verificable 1>
  - <criterio verificable 2>
Prerrequisitos:
  - <qué debe existir antes>
Riesgos:
  - <qué puede salir mal>
Bloqueos conocidos:
  - <qué puede impedir el cierre>
```

## Regla de alineación

Antes de proponer el bloque, verifica en `docs/as-is.md` que el alcance propuesto
no asume capacidades que no existen en el repo.

Si la petición implica capacidades marcadas como NO EXISTE en `docs/as-is.md`,
decláralas como prerrequisito o fuera del alcance del bloque.

## Regla de nomenclatura

Bloques de backend: `BACKEND-CONCEPTO-NNN`
Bloques de frontend: `FRONTEND-CONCEPTO-NNN`
Bloques de routing: `ROUTING-CONCEPTO-NNN` o `DEMO-CONCEPTO-NNN`
Bloques de infra/DB: `DB-CONCEPTO-NNN`
Bloques de docs: `DOCS-CONCEPTO-NNN`
