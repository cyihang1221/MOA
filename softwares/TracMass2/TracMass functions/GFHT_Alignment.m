function [hID hScore]=GFHT_Alignment(peakList,parameters,nSamp)
%Erik Tengstrand
Components=parameters.Components;
Penalty=parameters.Penalty;
Resolution=3;
TimeShift=parameters.TimeTolerance/60;
MinPeaks=1;
Opt=optimset('MaxIter',300,'Display','off');

[patterns PatternTimes]=GFHT_patterns(peakList);

gidc=getCollisions(peakList);
gidc(gidc==0)=[];
nCollisions = numel(gidc);
NextGid=max(peakList.gid)+1;
hID=peakList.gid;
hScore=zeros(size(peakList.gid));
Expected.Time=[];
Expected.ID=[];

%Creating sets of coefficients to fit GFHT
Points=Resolution^Components;
Coefficients=zeros(Points,Components);
Grid=-1.5:(3/(Resolution-1)):1.5;
for N=1:Components
    Coefficients(:,N)=repmat(sort(repmat(Grid',Resolution^(N-1),1)),Points/(Resolution^N),1);
end

WaitTotal=nCollisions;
ProgressHandle=waitbar(0,'Processing clusters');
setappdata(ProgressHandle,'canceling',0)
for N=1:nCollisions
    
    mask=peakList.gid == gidc(N);
    time=peakList.time(mask);
    samples=peakList.sample(mask);
    mask=find(mask);
    
    [~, index]=sort(abs(PatternTimes-mean(time)));
    NumberPatterns=min(numel(index),20);
    SelectedPatterns=patterns(:,index(1:NumberPatterns));
    [U,s,~] = svd(mean_center(SelectedPatterns));
    PCAPatterns=U(:,1:Components)*s(1:Components,1:Components);
    Constant=mean(time)+std(time)*Grid;
    
    %test until no more peaks can be grouped
    while numel(time)>=MinPeaks
        uSamp=unique(samples);
        
        Score=zeros(Points,Resolution);
        for P=1:Resolution
            for Q=1:Points;
                ScoreVector=GFHT_Score(Constant(P),Coefficients(Q,:),PCAPatterns,time,samples,TimeShift,uSamp);
                Score(Q,P)=sum(ScoreVector);
            end
        end
        [MaxScores, C1]=max(Score);
        [~,C2]=max(MaxScores);
        StartCoeffs(1)=Constant(C2);
        StartCoeffs(2:(Components+1))=Coefficients(C1(C2),:);
        
        %optimise the coefficients
        fcn=@(Coeffs)GFHT_Min(Coeffs(1),Coeffs(2:end),PCAPatterns,time,samples,TimeShift,nSamp,uSamp,Penalty);
        FinalCoeffs=fminsearch(fcn,StartCoeffs,Opt);
        [~, Peaks, PTime, Diff]=GFHT_Score(FinalCoeffs(1),FinalCoeffs(2:end),PCAPatterns,time,samples,TimeShift,uSamp);
        SelectedPeaks=find(Peaks.*(Diff<TimeShift));
        if numel(SelectedPeaks)==0
            break
        end
        
        %give the peaks a Hough ID and remove them from further testing
        hID(mask(SelectedPeaks))=NextGid;
        Expected.Time((end+1):(end+numel(PTime)))=PTime;
        Expected.ID((end+1):(end+numel(PTime)))=NextGid;
        NextGid=NextGid+1;
        hScore(mask(SelectedPeaks))=ScoreVector(SelectedPeaks);
        mask(SelectedPeaks)=[];
        time(SelectedPeaks)=[];
        samples(SelectedPeaks)=[];        
    end
    
    waitbar(N/WaitTotal,ProgressHandle);
end

delete(ProgressHandle)
