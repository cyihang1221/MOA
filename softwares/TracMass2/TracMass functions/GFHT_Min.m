function MinScore=GFHT_Min(Constant,Coefficients,PCAPatterns,time,samples,TimeShift,nSamp,uSamp,Penalty)
%Erik Tengstrand
penalty=sum(exp(Coefficients.^2))/100*sqrt(nSamp)*Penalty;
ScoreVector=GFHT_Score(Constant,Coefficients,PCAPatterns,time,samples,TimeShift,uSamp);
MinScore=penalty-sum(ScoreVector);