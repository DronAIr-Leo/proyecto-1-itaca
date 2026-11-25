# Práctica HDFS por dentro – Respuestas

Leonardo Darío Grifol Jordán

## 1. Explorar el clúster

1. Hay 6 DataNodes repartidos en 2 racks (dn1, dn2 y dn3 en rack1 y dn4, dn5 y dn6 en rack2). Cada uno tiene 2 GB, asi que la capacidad total configurada es de 12 GB.

2. ls muestra los ficheros del sistema local, o sea del disco de la maquina cliente del alumno. hdfs dfs -ls muestra el espacio de nombres de HDFS, que lo gestiona el NameNode, pero los datos de esos ficheros estan fisicamente repartidos en bloques en los discos de los DataNodes.

## 2. Subir un fichero y ver sus bloques

3. Tiene 3 bloques: dos de 128 MB y uno de 44 MB (128 + 128 + 44 = 300 MB).

4. Hay 9 replicas en total (3 bloques x 3 replicas) y ocupa 900 MB reales en el cluster, el triple del tamaño del fichero.

5. El bloque blk_1073741825 esta en dn4 (rack2), dn2 y dn3 (rack1). Si se cumple la politica por defecto: una replica en un rack y las otras dos juntas en otro rack distinto, asi aguanta la caida de un rack entero sin mover tantos datos entre racks.

6. No, el tamaño de bloque es un maximo. El ultimo bloque solo ocupa lo que tiene de datos, unos 44 MB, no reserva los 128 MB.

## 3. Tamaño de bloque y factor de replicación

7. ventas64.csv tiene 5 bloques (4 de 64 MB y uno de 44 MB). clientes.json tiene 1 bloque porque pesa 40 MB, y con replicacion 2 ocupa 80 MB en total.

8. La primera columna es el tamaño real del fichero y la segunda es el espacio que ocupa en disco contando todas las replicas. Por ejemplo ventas.csv sale 300 M y 900 M.

9. Da error porque el tamaño de bloque de 512k es menor que el minimo permitido (1 MB). Existe esta restriccion porque con bloques tan pequeños habria muchisimos bloques y el NameNode se llenaria de metadatos, ademas de mucho mas trafico y tareas.

10. Con bloques de 64 MB hay mas bloques, asi que se puede repartir mas el trabajo y procesar en paralelo con mas tareas. Pero el NameNode tiene que guardar el doble de metadatos y cada tarea tiene su coste de arranque, por eso para ficheros grandes suele ser mejor 128 MB o mas.

## 4. Lectura y operaciones de espacio de nombres

11. No cambia el espacio usado y no se copia ningun bloque. El -mv solo cambia la ruta en los metadatos del NameNode.

12. Con el -cp si sube el espacio usado, porque se crean bloques nuevos con sus replicas en los DataNodes. Es una copia real de los datos (300 MB mas por 3 replicas = 900 MB mas).

13. No, HDFS es de escribir una vez y leer muchas. No se puede modificar un trozo del medio, solo añadir al final con appendToFile o volver a escribir el fichero entero con los cambios.

## 5. Fallo de un DataNode y re-replicación

14. fsck sigue diciendo HEALTHY porque el NameNode todavia no sabe que dn1 se ha caido. Lo sigue viendo como LIVE hasta que pase el tiempo sin recibir heartbeats.

15. Pasa a STALE a los 30 segundos sin latidos y a DEAD despues de unos 10 minutos y medio (10.5 min) sin latidos.

16. Quedan infrarreplicados todos los bloques que tenia dn1, se ve en el fsck en Under-replicated blocks. El sistema los repara copiando cada bloque desde una replica que sigue viva a otro DataNode, respetando los racks, hasta volver a tener 3 copias. En el registro se ve que lo hace poco a poco, unas pocas re-replicaciones por paso.

17. No se pierde ningun dato porque cada bloque tenia otras 2 replicas. Cuando arranco dn1 otra vez manda sus bloques y hay replicas de mas, entonces el NameNode borra las que sobran para dejar 3.

## 6. Pérdida de datos: cuando la replicación no basta

18. El -cat da error porque no puede obtener el bloque, no hay ningun DataNode vivo con esa replica. Falla al momento, no hace falta esperar los 10 minutos, porque el cliente intenta leer del DataNode y esta parado.

19. Despues de avanzar el reloj fsck dice que el fichero esta CORRUPT, con bloques perdidos (missing blocks).

20. Si se recupera, porque los bloques seguian en el disco de esos DataNodes. Al arrancar mandan su informe de bloques al NameNode y el fichero vuelve a estar HEALTHY. No se habian borrado, solo no estaban disponibles.

21. Minimo 3 replicas, que es lo que viene por defecto. Asi aguanta que se caiga un nodo e incluso un rack entero. Con 1 replica cualquier fallo de un nodo es perdida de datos.

## 7. El problema de los ficheros pequeños

22. Se suben 500 ficheros y 500 bloques, y los objetos del NameNode suben unos 1000 (500 de ficheros + 500 de bloques). Todo esto para solo unos 49 MB de datos.

23. Un solo fichero de 50 MB genera solo 2 objetos: 1 fichero y 1 bloque.

24. 100 millones de ficheros de un bloque son 200 millones de objetos (fichero + bloque). A 150 bytes cada uno da unos 30 GB de memoria en el NameNode.

25. Juntar los ficheros pequeños en ficheros mas grandes antes de subirlos (por ejemplo en Parquet o SequenceFile), usar archivos HAR, o hacer procesos de compactacion que unan los ficheros pequeños cada cierto tiempo.

## 8. Ajustar la replicación y balancear el clúster

26. Al bajar a 2 el NameNode solo marca una replica como sobrante y la borra, es rapido. Al subir a 4 tiene que copiar una replica nueva por la red a otro DataNode, por eso tarda mas subir que bajar.

27. No, los bloques que ya estaban no se mueven solos a dn7. El nodo nuevo queda vacio y solo recibiria datos nuevos. Para repartirlos hay que usar el balancer.

28. El balanceador mira el porcentaje de uso de cada DataNode y lo compara con la media del cluster. Si un nodo se pasa del umbral (5%) por arriba o por abajo, mueve bloques de los mas llenos a los mas vacios. Al moverlos tiene que respetar la politica de colocacion, o sea no poner dos replicas en el mismo nodo ni dejar todas en el mismo rack.

## 9. Modo seguro (safe mode)

29. En modo seguro solo se puede leer: el -ls y el -cat funcionan. Las escrituras y cambios se rechazan, como subir notas.txt con -put o borrar con -rm.

30. Sirve para que al arrancar el NameNode espere a recibir los informes de bloques de los DataNodes antes de permitir cambios. Asi no empieza a re-replicar o borrar bloques pensando que faltan cuando en realidad los DataNodes todavia no se han reportado.

## 10. Reto final: sobrevivir a la caída de un rack

31. Si sigue siendo legible, porque por la politica de racks cada bloque tiene al menos una replica en el rack2, asi que se puede leer desde dn4, dn5 o dn6.

32. Los nodos del rack1 pasan a DEAD y el NameNode re-replica los bloques en los nodos del rack2 para volver a tener 3 copias. fsck vuelve a quedar sin bloques perdidos, pero todas las replicas estan ahora en el rack2. El problema es que si cae tambien el rack2 se pierde todo, ya no hay copia en otro rack.

33. Con replicacion 2 si se cumple, porque la segunda replica va a otro rack, y cuesta el doble de espacio (600 MB por cada 300 MB). Con replicacion 1 no se cumple, si la unica copia esta en el rack que se cae se pierde el fichero, aunque solo ocupa 1x. Con 3 es lo mas seguro pero ocupa el triple.

34. Si se cae el unico NameNode todo HDFS deja de funcionar, no se puede leer ni escribir nada porque nadie sabe donde estan los bloques, aunque los datos sigan en los DataNodes. Es un punto unico de fallo. Se mitiga con alta disponibilidad (HA): un NameNode standby que se sincroniza con JournalNodes y toma el control automaticamente con ZooKeeper, ademas de guardar copias del fsimage y los edits.
