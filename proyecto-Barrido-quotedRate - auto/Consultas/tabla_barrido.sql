# la tabla destinada a ser el nuevo almacen del barrido en vez de imprimir el barrido en un 
#archivo excel

SELECT TOP (1000) [Reserva]
      ,[QUOTED_RATE]
      ,[Rate]
      ,[Currency]
      ,[Fecha_Consulta]
  FROM [CatalogosYielding].[dbo].[Barrido_Quoted]