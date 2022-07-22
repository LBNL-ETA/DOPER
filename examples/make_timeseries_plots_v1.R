library(ggplot2)

  
gen_ts_plot <- function(tsdf, filename=NA, title=NA){
  
  colorList = c(
    '#2e6a95',
    '#2e6a95',
    '#3d3d3d',
    '#008000',
    '#a9a9a9',
    '#a9a9a9',
    '#86c5da',
    '#86c5da',
    '#e2c31d'
  )
  
  #create plots
  p<-ggplot(tsdf, aes(x=ts,y=value)) + 
    geom_area(aes(fill=src),alpha=0.8) +
    facet_grid(node ~ group) +
    # scale_x_continuous( expand = c(0,0) , limits = c(1,24),breaks = seq(0,24, by = 4) )+
    # scale_y_continuous( expand = c(0,0)) +
    scale_fill_manual(values=colorList) +
    ggtitle(title)+
    ylab('[kW]')+
    
    theme(
      panel.background = element_rect(fill = 'white', colour='white'),
      title = element_text(size = 18),
      plot.title = element_text(vjust = 2),
      # plot.margin = unit(c(1.2,1,1.2,1.2), "lines"),
      legend.position = "bottom",
      legend.background = element_rect(fill = "white"),
      legend.title=element_blank(),
      legend.text = element_text(size = 16),
      legend.key.width = unit(2.5, 'lines'),
      axis.text = element_text(size = 16),
      axis.text.y = element_text(size = 16),
      axis.title.y = element_text(vjust = 1),
      strip.text=element_text(vjust=1, size = 16),
      strip.background = element_rect(fill = 'white'),
      # panel.margin = unit(1, "lines")
    )
  
  
  if(!is.na(filename)){
    png(filename, width = 800, height = 1000)
    plot(p)
    dev.off()
  } else {
    plot(p)
  }
  
  return(p)
  
}

#################################

mainDir = 'C:/Users/nicholas/Desktop/controller files/doper_private/examples/test_results'
setwd(mainDir)

tsFile = 'test_results_R.csv'

tsData <- read.csv(tsFile, header = TRUE)

p2 = gen_ts_plot(tsData, filename='testPlot.png')

