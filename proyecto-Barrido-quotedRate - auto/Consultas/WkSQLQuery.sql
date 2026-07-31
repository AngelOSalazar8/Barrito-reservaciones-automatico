/****** Consulta parametrizada — el offset de dias se inyecta desde Python ******/
SELECT  [ReservationId]
      ,[Reservation] --
   FROM [dbAreaCorp].[dbo].[Reservaciones]
  WHERE Distribution_Channel_Details IN ('GDS', 'DYNAMIC TOUR', 'VOICE RES')
    AND Booking_Date >= CAST(DATEADD(DAY, -{DAYS_BACK}, GETDATE()) AS DATE);
